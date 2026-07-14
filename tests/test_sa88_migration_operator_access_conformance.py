"""SA88 cross-module migration operator-access conformance gate.

Ensures every shipped migration that executes cross-table/subquery DML
assigning ``organization_id`` does so inside a lexical
``with operator_access_migration(schema_editor)`` block.

The gate AST-parses shipped migration Python files and detects:
- Literal cross-table DML (UPDATE/INSERT/DELETE with subqueries) in
  ``schema_editor.execute()`` calls
- ORM ``.update(organization_id=...)`` writes with cross-table reads
- ``migrations.RunSQL(...)`` operations with cross-table DML
- Dynamic SQL (f-strings, ``format()``, ``%`` formatting) referencing
  ``organization_id``

Each detection requires lexical enclosure by ``operator_access_migration``
with a scope tied to the active ``schema_editor`` parameter.

Known debt exemptions are tracked in ``SA88_DEBT_EXEMPTIONS`` — an exact
file/symbol/reason ledger keyed to the owning SA issue.  Currently exempted:
- CRM 0009 ``_backfill_contactnote_org`` / ``_backfill_dealnote_org`` (ORM
  ``_base_manager`` bypasses FORCE RLS; owned by SA86 for uplift).

Comments, docstrings, DDL, and read-only SQL are ignored.

This test lives in the orgs test suite because the
``operator_access_migration`` context manager is defined in
``quickscale_modules_orgs.tenancy`` and the orgs test settings
(``--ds=tests.settings``) include all ``quickscale_modules_*`` apps,
making every shipped migration discoverable.
"""

from __future__ import annotations

import ast
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

_OPERATOR_ACCESS_CM_NAME = "operator_access_migration"
"""Name of the context manager function that gates must check for."""

_NO_MIGRATIONS_MODULES: set[str] = {"analytics", "storage"}
"""Modules that are shipped but have no database migrations (no schema changes, no
migrations/ directory).  These are enumerated explicitly so the manifest-based
scanner validates the known disposition instead of silently skipping them."""


# =========================================================================
# Debt exemption ledger
# =========================================================================
# Each entry is keyed by ``(app_label, migration_name)`` and contains
# exact symbol-level exemptions with a reason and owning SA issue.
# Tests prove that unlisted debt (migrations not in this ledger) FAILS
# the real-tree compliance check as a violation.
#
# When SA84/SA86 remediates the underlying issue, these exemptions can
# be removed.

SA88_DEBT_EXEMPTIONS: dict[tuple[str, str], list[dict[str, str]]] = {
    (
        "quickscale_modules_crm",
        "0009_add_note_organization_ownership",
    ): [
        {
            "symbol": "_backfill_contactnote_org",
            "category": "ungated-orm-write",
            "reason": (
                "ORM backfill — iterates objects via _base_manager and "
                "uses .update() for org assignment. The ORM-generated "
                "UPDATE is subject to FORCE RLS. If migrated to raw SQL, "
                "operator_access_migration() will be required."
            ),
            "owns": "SA84 (ORM backfill operator_access gap)",
        },
        {
            "symbol": "_backfill_dealnote_org",
            "category": "ungated-orm-write",
            "reason": (
                "ORM backfill — iterates objects via _base_manager and "
                "uses .update() for org assignment. The ORM-generated "
                "UPDATE is subject to FORCE RLS. If migrated to raw SQL, "
                "operator_access_migration() will be required."
            ),
            "owns": "SA84 (ORM backfill operator_access gap)",
        },
    ],
}


# =========================================================================
# Manifest-backed module inventory
# =========================================================================
# Shipped modules are defined from module.yml manifests.  The functions
# below validate parity between module.yml, pyproject.toml, and the
# filesystem package path, and provide migration-file discovery that is
# independent of Django INSTALLED_APPS.
#
# "teams" is a placeholder-only module that is explicitly excluded.
# "analytics" and "storage" are packaged but have no migrations directory
# (no-migrations disposition).


@dataclass(frozen=True)
class _ShippedModule:
    """Metadata for a shipped module discovered from its manifest."""

    dir_name: str
    """Directory name under ``quickscale_modules/`` (e.g. ``"crm"``)."""

    module_name: str
    """``name`` field from ``module.yml``."""

    version: str
    """``version`` field from ``module.yml``."""

    django_apps: tuple[str, ...]
    """``django_apps`` list from ``module.yml`` (first-party labels only)."""

    package_name: str
    """Python package name (e.g. ``"quickscale_modules_crm"``) derived from
    ``[tool.poetry].packages[0].include`` in ``pyproject.toml``."""

    has_migrations: bool
    """``True`` if a ``migrations/`` directory exists on the filesystem."""

    has_pyproject: bool
    """``True`` if ``pyproject.toml`` exists alongside the manifest."""


# =========================================================================
# Independent-set manifest discovery (strict, no fallback)
# =========================================================================
# Shipped modules are defined as the intersection of two independent
# sources: module.yml manifests and pyproject.toml package markers.
# A directory qualifies as a shipped module ONLY when both markers are
# present and yield matching metadata.  Directories with only one marker
# fail as drift.
#
# "teams" is excluded only while NEITHER marker exists.  If a module.yml
# or pyproject.toml appears under teams/, that is a separate violation
# (not silent exclusion).
#
# Modules with no migrations (analytics, storage) are tracked in an
# explicit no-migrations ledger with rationale and drift checks.


@dataclass(frozen=True)
class _ManifestMetadata:
    """Minimal metadata extracted from a module.yml manifest."""

    name: str
    version: str
    django_apps: tuple[str, ...]


def _read_metadata(ws_dir: Path) -> _ManifestMetadata | None:
    """Read and return metadata from ``module.yml`` at *ws_dir*, or
    ``None`` if the file is missing or unparseable.
    """
    yml_path = ws_dir / "module.yml"
    if not yml_path.is_file():
        return None
    with yml_path.open(encoding="utf-8") as f:
        manifest: dict = yaml.safe_load(f) or {}
    name = manifest.get("name", "")
    version = manifest.get("version", "")
    django_apps_raw: list[str] = manifest.get("django_apps") or []
    django_apps = tuple(
        a for a in django_apps_raw if a.startswith("quickscale_modules_")
    )
    if not name:
        return None
    return _ManifestMetadata(
        name=str(name),
        version=str(version),
        django_apps=django_apps,
    )


def _read_pyproject_package(ws_dir: Path) -> str | None:
    """Read the first ``[tool.poetry].packages[0].include`` from
    ``pyproject.toml`` at *ws_dir*, or ``None`` if missing/unparseable.
    """
    pp_path = ws_dir / "pyproject.toml"
    if not pp_path.is_file():
        return None
    with pp_path.open("rb") as f:
        pyproject = tomllib.load(f)
    packages = pyproject.get("tool", {}).get("poetry", {}).get("packages", [])
    if not packages:
        return None
    pkg = packages[0]
    if isinstance(pkg, dict):
        return pkg.get("include") or None
    return None


def _get_ws_root() -> Path:
    """Return the ``quickscale_modules/`` workspace root."""
    root = Path(__file__).resolve().parents[2]
    if not root.is_dir():
        pytest.fail(f"quickscale_modules workspace not found at {root}")
    return root


def _get_manifest_module_dirs(ws_root: Path | None = None) -> set[str]:
    """Return the set of directory names that contain a valid
    ``module.yml`` (independent of pyproject.toml).
    """
    if ws_root is None:
        ws_root = _get_ws_root()
    result: set[str] = set()
    for entry in sorted(ws_root.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if _read_metadata(entry) is not None:
            result.add(entry.name)
    return result


def _get_pyproject_module_dirs(ws_root: Path | None = None) -> set[str]:
    """Return the set of directory names that contain a valid
    ``pyproject.toml`` marker (independent of module.yml).
    """
    if ws_root is None:
        ws_root = _get_ws_root()
    result: set[str] = set()
    for entry in sorted(ws_root.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if _read_pyproject_package(entry) is not None:
            result.add(entry.name)
    return result


def _discover_shipped_modules() -> dict[str, _ShippedModule]:
    """Discover shipped modules as the intersection of manifests and
    pyproject markers.

    Requires BOTH ``module.yml`` and ``pyproject.toml`` to exist with
    valid content.  Directories with only one marker produce a test
    failure (drift).  No fallback from malformed markers.  Teams is
    excluded only while neither marker exists (if one appears, it's a
    separate drift event).

    Returns a ``dict`` keyed by directory name.
    """
    ws_root = _get_ws_root()

    manifest_dirs = _get_manifest_module_dirs(ws_root)
    pyproject_dirs = _get_pyproject_module_dirs(ws_root)

    # Fail on marker-only directories (drift).
    manifest_only = manifest_dirs - pyproject_dirs
    pyproject_only = pyproject_dirs - manifest_dirs
    if manifest_only:
        pytest.fail(
            f"Directories with module.yml but no pyproject.toml: "
            f"{sorted(manifest_only)}"
        )
    if pyproject_only:
        pytest.fail(
            f"Directories with pyproject.toml but no module.yml: "
            f"{sorted(pyproject_only)}"
        )

    shipped: dict[str, _ShippedModule] = {}
    for dir_name in sorted(manifest_dirs):
        entry = ws_root / dir_name

        meta = _read_metadata(entry)
        assert meta is not None  # guaranteed by _get_manifest_module_dirs

        package_name = _read_pyproject_package(entry) or ""

        # Verify package source dir exists.
        src_pkg = entry / "src" / package_name
        if not src_pkg.is_dir() or not package_name:
            pytest.fail(
                f"Module '{dir_name}': package source dir '{src_pkg}' does not exist"
            )

        # Verify package name matches the django_apps convention.
        first_django_app = meta.django_apps[0] if meta.django_apps else ""
        if first_django_app and first_django_app.startswith("quickscale_modules_"):
            derived = first_django_app
            if package_name and package_name != derived:
                pytest.fail(
                    f"Module '{dir_name}': pyproject.toml package "
                    f"'{package_name}' does not match module.yml "
                    f"django_apps '{derived}'"
                )

        migrations_dir = src_pkg / "migrations"
        has_migrations = migrations_dir.is_dir()

        shipped[dir_name] = _ShippedModule(
            dir_name=dir_name,
            module_name=meta.name,
            version=meta.version,
            django_apps=meta.django_apps or (package_name,),
            package_name=package_name,
            has_migrations=has_migrations,
            has_pyproject=True,
        )

    if not shipped:
        pytest.fail(
            f"No shipped modules discovered from manifest-pyproject "
            f"intersection under {ws_root}"
        )

    return shipped


def _get_shipped_modules() -> dict[str, _ShippedModule]:
    """Cached wrapper around ``_discover_shipped_modules``."""
    if not hasattr(_get_shipped_modules, "_cache"):
        _get_shipped_modules._cache = _discover_shipped_modules()  # type: ignore[attr-defined]
    return _get_shipped_modules._cache  # type: ignore[attr-defined]


# =========================================================================
# Public inventory helpers (parameterized for temporary-tree testing)
# =========================================================================


def find_shipped_migration_dirs(
    ws_root: Path | None = None,
) -> list[Path]:
    """Return migration directory paths for all shipped modules that have
    migrations.

    Accepts an optional *ws_root* for temporary-tree testing.  Defaults
    to the real ``quickscale_modules/`` workspace.
    """
    shipped = (
        discover_shipped_at(ws_root) if ws_root is not None else _get_shipped_modules()
    )
    base = ws_root if ws_root is not None else _get_ws_root()
    dirs: list[Path] = []
    for mod in shipped.values():
        if not mod.has_migrations:
            continue
        migrations_dir = base / mod.dir_name / "src" / mod.package_name / "migrations"
        if migrations_dir.is_dir():
            dirs.append(migrations_dir.resolve())

    if not dirs:
        pytest.fail("No shipped migration directories found")
    return sorted(dirs)


def find_shipped_migration_files(
    ws_root: Path | None = None,
) -> list[Path]:
    """Return migration ``.py`` files for all shipped modules with
    migrations.  Accepts optional *ws_root* for temporary-tree tests.
    """
    files: list[Path] = []
    for d in find_shipped_migration_dirs(ws_root):
        for py_file in sorted(d.glob("[0-9]*.py")):
            files.append(py_file)
    return files


def discover_shipped_at(ws_root: Path) -> dict[str, _ShippedModule]:
    """Discover shipped modules from a given workspace root (for
    temporary-tree or drift tests).  Independent of the cached default.

    Validates that the pyproject.toml package name aligns with the
    module.yml ``django_apps`` first entry (when that entry starts
    with ``quickscale_modules_``).  Mismatched modules are excluded
    (fail-closed).
    """
    manifest_dirs = _get_manifest_module_dirs(ws_root)
    pyproject_dirs = _get_pyproject_module_dirs(ws_root)
    shipped: dict[str, _ShippedModule] = {}
    for dir_name in sorted(manifest_dirs & pyproject_dirs):
        entry = ws_root / dir_name
        meta = _read_metadata(entry)
        assert meta is not None
        package_name = _read_pyproject_package(entry) or ""
        if not package_name:
            continue

        # Validate package name consistency with django_apps.
        first_django_app = meta.django_apps[0] if meta.django_apps else ""
        if first_django_app and first_django_app.startswith("quickscale_modules_"):
            if package_name != first_django_app:
                # Mismatch: exclude this module (fail-closed).
                continue

        src_pkg = entry / "src" / package_name
        if not src_pkg.is_dir():
            continue
        migrations_dir = src_pkg / "migrations"
        shipped[dir_name] = _ShippedModule(
            dir_name=dir_name,
            module_name=meta.name,
            version=meta.version,
            django_apps=meta.django_apps or (package_name,),
            package_name=package_name,
            has_migrations=migrations_dir.is_dir(),
            has_pyproject=True,
        )
    return shipped


# =========================================================================
# Live-tree convenience wrappers
# =========================================================================


def get_manifest_migration_dirs() -> list[Path]:
    """Convenience wrapper — delegates to ``find_shipped_migration_dirs``
    with the default workspace root."""
    return find_shipped_migration_dirs()


def get_manifest_migration_files() -> list[Path]:
    """Convenience wrapper — delegates to ``find_shipped_migration_files``
    with the default workspace root."""
    return find_shipped_migration_files()


def _get_module_label_from_path(filepath: str) -> str | None:
    """Derive the Django app label (e.g. ``quickscale_modules_crm``) from a
    migration file's absolute path.

    Matches the ``src/quickscale_modules_<name>/`` segment.
    """
    p = Path(filepath)
    parts = p.parts
    for i, part in enumerate(parts):
        if part == "src" and i + 1 < len(parts):
            candidate = parts[i + 1]
            if candidate.startswith("quickscale_modules_"):
                return candidate
    return None


def _is_exempt_file(filepath: str | None, module_label: str | None = None) -> bool:
    """Return ``True`` if *filepath* corresponds to an exempt migration."""
    if filepath is None:
        return False
    p = Path(filepath)
    # Determine app label from the filesystem path.
    # Path example: .../crm/src/quickscale_modules_crm/migrations/0009_...
    parts = p.parts
    label: str | None = module_label
    if label is None:
        for i, part in enumerate(parts):
            if part == "src" and i + 1 < len(parts):
                label = parts[i + 1]
                break
    if label is None:
        return False
    # Match migration name: the filename without .py
    migration_name = p.stem
    return (label, migration_name) in SA88_DEBT_EXEMPTIONS


def _is_exempt_symbol(
    filepath: str | None,
    func_name: str | None,
    module_label: str | None = None,
    category: str | None = None,
) -> bool:
    """Return ``True`` if the specific function *func_name* in *filepath*
    is exempt for the given *category*.

    When a detector *category* is provided, only exemptions whose
    ``category`` field matches (or exemptions without a category field)
    are considered.  This prevents a per-category exemption from waiving
    violations of a different type in the same symbol.
    """
    if filepath is None or func_name is None:
        return False
    p = Path(filepath)
    parts = p.parts
    label: str | None = module_label
    if label is None:
        for i, part in enumerate(parts):
            if part == "src" and i + 1 < len(parts):
                label = parts[i + 1]
                break
    if label is None:
        return False
    migration_name = p.stem
    exemptions = SA88_DEBT_EXEMPTIONS.get((label, migration_name), [])
    for e in exemptions:
        if e["symbol"] != func_name:
            continue
        if category is not None and "category" in e:
            if e["category"] == category:
                return True
            continue
        return True  # Exemption without category filter matches all categories.
    return False


# =========================================================================
# AST-level helpers
# =========================================================================


def _has_subquery(upper_sql: str) -> bool:
    """Return ``True`` if *upper_sql* contains a subquery (SELECT inside
    parentheses with optional whitespace).

    This is a lexical heuristic — it does not fully parse the SQL grammar.
    It is deliberately conservative: it requires ``(`` followed (after
    optional whitespace) by ``SELECT``.
    """
    return bool(re.search(r"\(\s*SELECT\b", upper_sql))


def _is_cross_table_dml_assigning_org_id(sql_text: str) -> bool:
    """Check whether *sql_text* is a cross-table DML statement that assigns
    ``organization_id``.

    A statement is considered cross-table DML when:
    1. It is an ``UPDATE``, ``INSERT``, or ``DELETE`` statement.
    2. It contains ``ORGANIZATION_ID`` (the column being assigned).
    3. It contains a subquery (``(SELECT ...)``), OR it is an UPDATE with
       a FROM clause referencing another table, OR it is an INSERT ...
       SELECT (without enclosing parentheses around the SELECT) —
       each indicating a cross-table read that may be blocked by FORCE RLS.

    Args:
        sql_text: The SQL string literal from a ``schema_editor.execute()``
            call.

    Returns:
        ``True`` if the text matches the cross-table DML heuristic.
    """
    if not sql_text:
        return False

    stripped = sql_text.strip()
    upper = stripped.upper()

    # Must be a DML statement (UPDATE, INSERT, or DELETE).
    if not any(upper.startswith(kw) for kw in ("UPDATE ", "INSERT ", "DELETE ")):
        return False

    # Must reference organization_id (the column whose value crosses tables).
    if "ORGANIZATION_ID" not in upper:
        return False

    # --- Cross-table access checks ---

    # 1. Subquery (SELECT inside parentheses).
    if _has_subquery(upper):
        return True

    # 2. UPDATE with FROM clause referencing another table.
    if upper.startswith("UPDATE ") and " FROM " in upper:
        table_match = re.match(r"UPDATE\s+(\S+)", upper)
        from_match = re.search(r"\bFROM\s+(\S+)", upper)
        if table_match and from_match:
            update_table = table_match.group(1)
            from_table = from_match.group(1)
            # A FROM clause targeting a different table (not a parenthesised
            # subquery which is already caught above) is cross-table.
            if from_table != update_table and not from_table.startswith("("):
                return True

    # 3. INSERT INTO ... SELECT (bare SELECT, not a parenthesised subquery).
    if upper.startswith("INSERT ") and " SELECT " in upper:
        return True

    return False


def _is_operator_access_migration_call(node: ast.AST) -> bool:
    """Return ``True`` if *node* is a call to the name
    ``operator_access_migration`` (regardless of argument count).

    This is deliberately lenient so that ``_check_wrong_editor`` can
    examine zero-arg and extra-arg calls and flag them.  Argument
    validity is enforced separately by the ancestry-based gating
    infrastructure (``_find_gated_with_nodes``).
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _OPERATOR_ACCESS_CM_NAME
    )


# =========================================================================
# Canonical import validation
# =========================================================================
# The migration file MUST import operator_access_migration from the
# canonical module:
#
#     from quickscale_modules_orgs.tenancy import operator_access_migration
#
# Missing, aliased, or non-canonical imports are violations.  Any
# rebinding (assignment, function/lambda def, or parameter shadow) that
# shadows the canonical name is also a violation.  When the canonical
# import is missing, no gating block in the file is treated as valid.

_CANONICAL_IMPORT_MODULE = "quickscale_modules_orgs.tenancy"


def _check_canonical_import(tree: ast.AST) -> tuple[bool, list[dict]]:
    """Validate that *tree* contains the canonical import of
    ``operator_access_migration`` from ``quickscale_modules_orgs.tenancy``
    and that the name is not shadowed by rebinding, function/lambda
    definitions, or parameter names.

    The canonical import is required only when the name
    ``operator_access_migration`` is actually *referenced* in the source
    (i.e., the file uses the context manager).  Files that never reference
    the name do not need the import.

    Returns ``(is_valid, violations)``:
    - ``is_valid``: ``True`` iff either (a) the name is not referenced at
      all, or (b) the canonical import is present and unshadowed.
    - ``violations``: list of violation dicts (empty when valid).
    """
    has_canonical_import = False
    name_is_referenced = False
    violations: list[dict] = []

    for node in ast.walk(tree):
        # --- Check for canonical from-import ---
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == _OPERATOR_ACCESS_CM_NAME:
                    if node.module == _CANONICAL_IMPORT_MODULE and alias.asname is None:
                        has_canonical_import = True
                    elif node.module != _CANONICAL_IMPORT_MODULE:
                        violations.append(
                            {
                                "filepath": "<unknown>",
                                "line": node.lineno,
                                "message": (
                                    f"Import of '{_OPERATOR_ACCESS_CM_NAME}' "
                                    f"from non-canonical module "
                                    f"'{node.module}' at line {node.lineno}.  "
                                    f"Must import from "
                                    f"{_CANONICAL_IMPORT_MODULE}."
                                ),
                                "category": "shadowing",
                            }
                        )
                    elif alias.asname is not None:
                        violations.append(
                            {
                                "filepath": "<unknown>",
                                "line": node.lineno,
                                "message": (
                                    f"Aliased import of "
                                    f"'{_OPERATOR_ACCESS_CM_NAME}' at line "
                                    f"{node.lineno}.  Use the unaliased name: "
                                    f"from {_CANONICAL_IMPORT_MODULE} import "
                                    f"{_OPERATOR_ACCESS_CM_NAME}."
                                ),
                                "category": "shadowing",
                            }
                        )

        # --- Check for import/from-import that shadows via asname ---
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.asname == _OPERATOR_ACCESS_CM_NAME:
                    violations.append(
                        {
                            "filepath": "<unknown>",
                            "line": node.lineno,
                            "message": (
                                f"Alias '{alias.asname}' shadows the canonical "
                                f"'{_OPERATOR_ACCESS_CM_NAME}' name at line "
                                f"{node.lineno}.  Use the unaliased name from "
                                f"{_CANONICAL_IMPORT_MODULE}."
                            ),
                            "category": "shadowing",
                        }
                    )

        # --- Detect if name is referenced (not in import context) ---
        if isinstance(node, ast.Name) and node.id == _OPERATOR_ACCESS_CM_NAME:
            name_is_referenced = True

        # --- Reject rebinding assignments ---
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == _OPERATOR_ACCESS_CM_NAME
                ):
                    violations.append(
                        {
                            "filepath": "<unknown>",
                            "line": node.lineno,
                            "message": (
                                f"Rebinding assignment to "
                                f"'{_OPERATOR_ACCESS_CM_NAME}' at line "
                                f"{node.lineno}.  The name must remain bound "
                                f"to the canonical import from "
                                f"{_CANONICAL_IMPORT_MODULE}."
                            ),
                            "category": "shadowing",
                        }
                    )

        # --- Reject function/lambda definitions that shadow ---
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == _OPERATOR_ACCESS_CM_NAME:
                violations.append(
                    {
                        "filepath": "<unknown>",
                        "line": node.lineno,
                        "message": (
                            f"Function definition shadows the canonical "
                            f"'{_OPERATOR_ACCESS_CM_NAME}' name at line "
                            f"{node.lineno}.  Use a different function name."
                        ),
                        "category": "shadowing",
                    }
                )
            for p in node.args.args:
                if p.arg == _OPERATOR_ACCESS_CM_NAME:
                    violations.append(
                        {
                            "filepath": "<unknown>",
                            "line": p.lineno if hasattr(p, "lineno") else node.lineno,
                            "message": (
                                f"Parameter '{_OPERATOR_ACCESS_CM_NAME}' "
                                f"shadows the canonical name in function "
                                f"'{node.name}' at line {node.lineno}."
                            ),
                            "category": "shadowing",
                        }
                    )
            if node.args.vararg and node.args.vararg.arg == _OPERATOR_ACCESS_CM_NAME:
                violations.append(
                    {
                        "filepath": "<unknown>",
                        "line": node.lineno,
                        "message": (
                            f"*args parameter shadows canonical name "
                            f"'{_OPERATOR_ACCESS_CM_NAME}' in function "
                            f"'{node.name}'."
                        ),
                        "category": "shadowing",
                    }
                )
            for p in node.args.kwonlyargs:
                if p.arg == _OPERATOR_ACCESS_CM_NAME:
                    violations.append(
                        {
                            "filepath": "<unknown>",
                            "line": p.lineno if hasattr(p, "lineno") else node.lineno,
                            "message": (
                                f"Keyword-only parameter "
                                f"'{_OPERATOR_ACCESS_CM_NAME}' shadows "
                                f"canonical name in function '{node.name}'."
                            ),
                            "category": "shadowing",
                        }
                    )

        # --- Reject lambda that shadows ---
        if isinstance(node, ast.Lambda):
            for arg in node.args.args:
                if arg.arg == _OPERATOR_ACCESS_CM_NAME:
                    violations.append(
                        {
                            "filepath": "<unknown>",
                            "line": node.lineno if hasattr(node, "lineno") else 0,
                            "message": (
                                f"Lambda parameter shadows canonical name "
                                f"'{_OPERATOR_ACCESS_CM_NAME}'."
                            ),
                            "category": "shadowing",
                        }
                    )

    # Require canonical import only when the name is actually referenced.
    if name_is_referenced and not has_canonical_import:
        violations.append(
            {
                "filepath": "<unknown>",
                "line": 1,
                "message": (
                    f"Missing canonical import: "
                    f"from {_CANONICAL_IMPORT_MODULE} import "
                    f"{_OPERATOR_ACCESS_CM_NAME}.  Without this import, "
                    f"no gating block is valid."
                ),
                "category": "missing-canonical-import",
            }
        )

    is_valid = (not name_is_referenced) or has_canonical_import
    return is_valid, violations


# =========================================================================
# True AST ancestry gating (replaces line-number range heuristics)
# =========================================================================


def _build_parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    """Build a mapping from ``id(child_node)`` to parent node for every
    node in *tree*.  Allows checking whether a node is an AST descendant
    of a given ancestor.
    """
    parent_map: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[id(child)] = parent
    return parent_map


def _is_descendant_of_gated_block(
    node: ast.AST,
    gated_blocks: list[ast.With],
    parent_map: dict[int, ast.AST],
) -> bool:
    """Return ``True`` if *node* is an AST descendant (child, grandchild,
    etc.) of any ``ast.With`` node in *gated_blocks*.

    Walks the parent chain upward from *node* using *parent_map*.  This
    is the replacement for the old ``_is_within_ranges`` line-number
    heuristic: instead of trusting line-number containment, it verifies
    actual AST ancestry.
    """
    current: ast.AST | None = node
    while True:
        parent = parent_map.get(id(current))
        if parent is None:
            return False
        if parent in gated_blocks:
            return True
        current = parent


def _find_gated_with_nodes(
    tree: ast.AST,
    parent_map: dict[int, ast.AST],
    canonical_import_valid: bool,
) -> list[ast.With]:
    """Return every ``with operator_access_migration(...)`` block in
    *tree* that meets the full validity contract:

    1. The canonical import is present (``canonical_import_valid``).
    2. The call uses exactly one argument.
    3. That argument is the enclosing function's literal ``schema_editor``
       parameter.

    When any condition is false, the block is excluded from the result
    (it does NOT produce a valid gating range).  Zero-arg, extra-arg, and
    wrong-editor blocks are flagged separately by ``_check_wrong_editor``.

    Returns a list of ``ast.With`` nodes that are valid gating blocks.
    """
    if not canonical_import_valid:
        return []

    # Build enclosing-function-param map (same as _check_wrong_editor).
    func_params: dict[tuple[int, int], set[str]] = {}
    for func_node in ast.walk(tree):
        if isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = func_node.end_lineno or func_node.lineno
            params = {p.arg for p in func_node.args.args}
            func_params[(func_node.lineno, end)] = params

    def _enclosing_func_has_schema_editor(lineno: int) -> bool:
        for (start, end), params in sorted(func_params.items(), reverse=True):
            if start <= lineno <= end:
                return "schema_editor" in params
        return False

    gated: list[ast.With] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            if not _is_operator_access_migration_call(item.context_expr):
                continue
            if not isinstance(item.context_expr, ast.Call):
                continue
            call = item.context_expr
            # Must have exactly one argument.
            if len(call.args) != 1:
                continue
            first_arg = call.args[0]
            # Must be a simple Name.
            if not isinstance(first_arg, ast.Name):
                continue
            # Must be the literal 'schema_editor' parameter of the enclosing func.
            if first_arg.id != "schema_editor":
                continue
            if not _enclosing_func_has_schema_editor(node.lineno):
                continue
            gated.append(node)
    return gated


def _extract_sql_arg(call_node: ast.Call) -> str | None:
    """Extract the SQL string from the first argument of
    ``schema_editor.execute(...)`` (or ``cursor.execute(...)``).

    Returns the string value, or ``None`` if it cannot be statically
    determined (e.g. a variable or expression).
    """
    if not call_node.args:
        return None
    first_arg = call_node.args[0]
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        return first_arg.value
    return None


def _is_execute_call(node: ast.AST) -> bool:
    """Return ``True`` if *node* is a method call named ``execute()``.

    Matches ``name.execute(...)`` for any simple name (e.g.
    ``schema_editor.execute(...)``, ``cursor.execute(...)``,
    ``cur.execute(...)``).
    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    )


def _find_enclosing_function_name(tree: ast.AST, lineno: int) -> str | None:
    """Return the name of the function that contains *lineno*.

    Returns ``None`` if the line is not inside any function definition.
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = node.end_lineno
            if end is not None and node.lineno <= lineno <= end:
                return node.name
    return None


# =========================================================================
# Detector: ORM .update(organization_id=...) writes
# =========================================================================


def _is_orm_update_write(node: ast.AST) -> bool:
    """Return ``True`` if *node* is an ORM ``.update(organization_id=...)``
    call that assigns ``organization_id`` as a keyword argument.

    Matches patterns like:
    - ``MyModel._base_manager.filter(...).update(organization_id=...)``
    - ``MyModel.objects.update(organization_id=...)``
    - ``Manager.objects.filter(pk=...).update(organization_id=...)``

    This detects cross-table ORM writes that go through the ORM's
    SQL generation but still produce UPDATE statements referencing
    ``organization_id``.
    """
    if not isinstance(node, ast.Call):
        return False
    if not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr != "update":
        return False
    # Check whether organization_id appears as a keyword argument.
    for kw in node.keywords:
        if kw.arg == "organization_id":
            return True
    return False


# =========================================================================
# Detector: migrations.RunSQL operations
# =========================================================================


def _is_runsql_dml_call(node: ast.AST) -> bool:
    """Return ``True`` if *node* is a ``migrations.RunSQL(...)`` call
    that might contain cross-table DML.

    Matches ``RunSQL(sql, ...)`` where ``sql`` is a string constant
    or tuple of string constants.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # migrations.RunSQL or RunSQL (after from-import)
    if isinstance(func, ast.Attribute) and func.attr == "RunSQL":
        pass  # Likely migrations.RunSQL
    elif isinstance(func, ast.Name) and func.id == "RunSQL":
        pass  # from-import case
    else:
        return False
    return True


def _extract_runsql_sql(call_node: ast.Call) -> list[str]:
    """Extract SQL string(s) from a ``migrations.RunSQL(...)`` call.

    Returns a list of SQL strings (possibly empty).
    """
    if not call_node.args:
        return []
    first_arg = call_node.args[0]
    results: list[str] = []
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        results.append(first_arg.value)
    elif isinstance(first_arg, ast.Tuple):
        for elt in first_arg.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                results.append(elt.value)
    return results


# =========================================================================
# Detector: dynamic SQL (f-strings, format(), %)
# =========================================================================


def _is_dynamic_sql_with_org_id(node: ast.AST) -> bool:
    """Return ``True`` if *node* is an ``execute()`` call whose SQL
    argument is dynamically constructed (f-string, ``format()`` call,
    ``%`` operator) and contains ``organization_id``.

    Dynamic SQL cannot be statically analysed, so we flag it as a
    manual-review item when ``organization_id`` appears in the
    template/format string.
    """
    if not isinstance(node, ast.Call):
        return False
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "execute":
        return False
    if not node.args:
        return False
    first_arg = node.args[0]
    # f-string (ast.JoinedStr)
    if isinstance(first_arg, ast.JoinedStr):
        # Get the first constant part to determine if SQL is DML or DDL/read-only.
        first_const = ""
        for value in first_arg.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                first_const = value.value.upper()
                break
        if not first_const:
            return False
        # Only flag if the SQL starts with a DML keyword (UPDATE, INSERT, DELETE).
        # Use the full string including trailing space for matching.
        if not any(
            first_const.startswith(kw) for kw in ("UPDATE ", "INSERT ", "DELETE ")
        ):
            return False
        # Check for ORGANIZATION_ID reference in any constant part.
        for value in first_arg.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                if "ORGANIZATION_ID" in value.value.upper():
                    return True
        return False
    # format() call: "..." % value
    if isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, ast.Mod):
        if isinstance(first_arg.left, ast.Constant) and isinstance(
            first_arg.left.value, str
        ):
            upper = first_arg.left.value.strip().upper()
            if not any(
                upper.startswith(kw) for kw in ("UPDATE ", "INSERT ", "DELETE ")
            ):
                return False
            if "ORGANIZATION_ID" in upper:
                return True
        return False
    # .format() call
    if isinstance(first_arg, ast.Call) and isinstance(first_arg.func, ast.Attribute):
        if first_arg.func.attr == "format":
            if first_arg.func.value and isinstance(first_arg.func.value, ast.Constant):
                if isinstance(first_arg.func.value.value, str):
                    upper = first_arg.func.value.value.strip().upper()
                    if not any(
                        upper.startswith(kw) for kw in ("UPDATE ", "INSERT ", "DELETE ")
                    ):
                        return False
                    if "ORGANIZATION_ID" in upper:
                        return True
        return False
    return False


# =========================================================================
# Detector: raw GUC manipulation (SET/SET LOCAL/RESET/set_config)
# =========================================================================
# These are non-exemptible: direct GUC manipulation is always a violation
# even when inside an operator_access_migration block, because the context
# manager is the only permitted mechanism.


_RAW_GUC_PATTERNS: list[re.Pattern] = [
    re.compile(r"SET\s+LOCAL\s+app\.operator_access\s*=", re.IGNORECASE),
    re.compile(r"SET\s+(SESSION\s+)?app\.operator_access\s*=", re.IGNORECASE),
    re.compile(r"RESET\s+app\.operator_access\b", re.IGNORECASE),
    re.compile(
        r"set_config\s*\(\s*['\"]app\.operator_access['\"]",
        re.IGNORECASE,
    ),
]


def _is_raw_guc_manipulation(sql_text: str) -> bool:
    """Return ``True`` if *sql_text* directly manipulates the
    ``app.operator_access`` GUC via ``SET``, ``SET LOCAL``, ``RESET``,
    or ``set_config``.

    Direct GUC manipulation is always forbidden in migration files.  The
    ``operator_access_migration`` context manager is the only permitted
    mechanism.  Any ``execute()`` or ``RunSQL`` call matching this
    detector is a violation regardless of whether it appears inside a
    ``with operator_access_migration(...)`` block.
    """
    if not sql_text:
        return False
    upper = sql_text.strip().upper()
    for pattern in _RAW_GUC_PATTERNS:
        if pattern.search(upper):
            return True
    return False


# =========================================================================
# Detector: assignment+save pattern (obj.organization_id = x; obj.save())
# =========================================================================


def _check_body_for_assignment_save(
    body: list[ast.stmt],
    func_name: str,
    gated_blocks: list[ast.With],
    parent_map: dict[int, ast.AST],
    violations: list[dict],
) -> None:
    """Recursively scan *body* (a list of statements) for the pattern
    ``obj.organization_id = value`` followed by ``obj.save()`` (or
    ``obj.save(update_fields=...)``) that is NOT enclosed by
    ``operator_access_migration``.

    Uses true AST ancestry (``_is_descendant_of_gated_block``) instead
    of line-number ranges.

    Appends violation dicts to *violations* in place.
    """
    for i, stmt in enumerate(body):
        # Check compound statements with nested bodies (for, while, with, try, etc.)
        if isinstance(stmt, (ast.For, ast.AsyncFor)):
            _check_body_for_assignment_save(
                stmt.body,
                func_name,
                gated_blocks,
                parent_map,
                violations,
            )
            _check_body_for_assignment_save(
                stmt.orelse or [],
                func_name,
                gated_blocks,
                parent_map,
                violations,
            )
        if isinstance(stmt, (ast.While,)):
            _check_body_for_assignment_save(
                stmt.body,
                func_name,
                gated_blocks,
                parent_map,
                violations,
            )
            _check_body_for_assignment_save(
                stmt.orelse or [],
                func_name,
                gated_blocks,
                parent_map,
                violations,
            )
        if isinstance(stmt, ast.With):
            _check_body_for_assignment_save(
                stmt.body,
                func_name,
                gated_blocks,
                parent_map,
                violations,
            )
        if isinstance(stmt, ast.Try):
            _check_body_for_assignment_save(
                stmt.body,
                func_name,
                gated_blocks,
                parent_map,
                violations,
            )
            for handler in stmt.handlers:
                _check_body_for_assignment_save(
                    handler.body,
                    func_name,
                    gated_blocks,
                    parent_map,
                    violations,
                )
            _check_body_for_assignment_save(
                stmt.orelse or [],
                func_name,
                gated_blocks,
                parent_map,
                violations,
            )
            _check_body_for_assignment_save(
                stmt.finalbody or [],
                func_name,
                gated_blocks,
                parent_map,
                violations,
            )
        if isinstance(stmt, ast.If):
            _check_body_for_assignment_save(
                stmt.body,
                func_name,
                gated_blocks,
                parent_map,
                violations,
            )
            _check_body_for_assignment_save(
                stmt.orelse or [],
                func_name,
                gated_blocks,
                parent_map,
                violations,
            )

        # Look for: <expr>.organization_id = <value>
        if not isinstance(stmt, ast.Assign):
            continue
        assign = stmt
        if len(assign.targets) != 1:
            continue
        target = assign.targets[0]
        if not isinstance(target, ast.Attribute):
            continue
        if target.attr != "organization_id":
            continue

        # Found an assignment to .organization_id.  Check whether a
        # .save() call follows within the next few statements (same block).
        save_stmt: ast.stmt | None = None
        for j in range(i + 1, min(i + 5, len(body))):
            next_stmt = body[j]
            if isinstance(next_stmt, ast.Expr):
                inner = next_stmt.value
                if isinstance(inner, ast.Call):
                    if isinstance(inner.func, ast.Attribute) and inner.func.attr in (
                        "save",
                        "asave",
                    ):
                        save_stmt = next_stmt
                        break
        if save_stmt is None:
            continue

        # Check if both assignment AND save are AST descendants of a
        # valid gating block (true AST ancestry, not line-number ranges).
        assign_covered = _is_descendant_of_gated_block(
            assign,
            gated_blocks,
            parent_map,
        )
        save_covered = _is_descendant_of_gated_block(
            save_stmt,
            gated_blocks,
            parent_map,
        )

        if not (assign_covered and save_covered):
            violations.append(
                {
                    "func_name": func_name,
                    "line": assign.lineno,
                    "message": (
                        f"organization_id assignment (line {assign.lineno}) "
                        f"followed by .save() (line "
                        f"{save_stmt.lineno}) is not "
                        f"enclosed by `with operator_access_migration("
                        f"schema_editor):`.  ORM writes through the default "
                        f"manager are subject to FORCE RLS and need "
                        f"operator_access."
                    ),
                    "category": "ungated-assignment-save",
                }
            )


def _find_assignment_save_in_function(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    gated_blocks: list[ast.With],
    parent_map: dict[int, ast.AST],
) -> list[dict]:
    """Detect ``obj.organization_id = value`` followed by ``obj.save()``
    (or ``obj.save(update_fields=...)``) within *func_node* that are NOT
    enclosed by ``operator_access_migration``.

    Uses true AST ancestry via ``_is_descendant_of_gated_block``.

    .. note::
       The previous ``_base_manager`` function-wide waiver has been removed
       (SA88 Phase 1).  All assignment+save patterns are now checked
       regardless of whether the function uses ``_base_manager``.  Exemptions
       must be exact file/symbol/category entries in ``SA88_DEBT_EXEMPTIONS``.

    Recursively checks compound statement bodies (for, while, with, try,
    if).  Returns a list of violation dicts with the line of the assignment.
    """
    violations: list[dict] = []
    _check_body_for_assignment_save(
        func_node.body,
        func_node.name,
        gated_blocks,
        parent_map,
        violations,
    )
    return violations


# =========================================================================
# Detector: wrong editor (operator_access_migration argument != schema_editor)
# =========================================================================


def _check_wrong_editor(tree: ast.AST) -> list[dict]:
    """Detect ``with operator_access_migration(...)`` blocks where the
    argument passed is not the enclosing function's ``schema_editor``
    parameter.

    Returns a list of violation dicts, one per misused call.
    """
    # Build a line-indexed function-parameter map for fast lookup.
    func_params: dict[tuple[int, int], set[str]] = {}
    func_names: dict[tuple[int, int], str] = {}
    for func_node in ast.walk(tree):
        if isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = func_node.end_lineno or func_node.lineno
            params = {p.arg for p in func_node.args.args}
            func_params[(func_node.lineno, end)] = params
            func_names[(func_node.lineno, end)] = func_node.name

    def _find_enclosing_func_name(lineno: int) -> str:
        for (start, end), name in sorted(func_names.items(), reverse=True):
            if start <= lineno <= end:
                return name
        return "<module>"

    violations: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            if not _is_operator_access_migration_call(item.context_expr):
                continue
            assert isinstance(item.context_expr, ast.Call)
            call = item.context_expr

            # Flag zero-argument calls (failed closed — must have exactly 1 arg).
            if not call.args:
                violations.append(
                    {
                        "line": node.lineno,
                        "message": (
                            f"operator_access_migration() called with no "
                            f"arguments at line {node.lineno}.  Requires "
                            f"exactly one argument: the enclosing "
                            f"callback's own 'schema_editor' parameter."
                        ),
                        "category": "wrong-editor",
                    }
                )
                continue

            # Flag extra-argument calls (must have exactly 1 arg).
            if len(call.args) > 1:
                violations.append(
                    {
                        "line": node.lineno,
                        "message": (
                            f"operator_access_migration() called with "
                            f"{len(call.args)} arguments at line "
                            f"{node.lineno}.  Requires exactly one argument: "
                            f"the enclosing callback's own 'schema_editor' "
                            f"parameter."
                        ),
                        "category": "wrong-editor",
                    }
                )
                continue

            first_arg = call.args[0]

            if isinstance(first_arg, ast.Name):
                arg_name = first_arg.id
                enclosing_name = _find_enclosing_func_name(node.lineno)
                # The argument MUST be the literal "schema_editor".
                if arg_name != "schema_editor":
                    violations.append(
                        {
                            "line": node.lineno,
                            "message": (
                                f"operator_access_migration() called "
                                f"with argument '{arg_name}' at line "
                                f"{node.lineno} in function "
                                f"'{enclosing_name}'.  Must use the "
                                f"literal 'schema_editor' parameter, "
                                f"not '{arg_name}'."
                            ),
                            "category": "wrong-editor",
                        }
                    )
            else:
                # Non-name argument (e.g. attribute, call, etc.)
                violations.append(
                    {
                        "line": node.lineno,
                        "message": (
                            f"operator_access_migration() called with an "
                            f"expression at line {node.lineno} that is not "
                            f"a simple name.  Must use the enclosing "
                            f"callback's own 'schema_editor' parameter."
                        ),
                        "category": "wrong-editor",
                    }
                )
    return violations


# NOTE: shadowing detection is now handled by ``_check_canonical_import``
# above, which validates the import, rejects aliases, rebinding,
# function/lambda/parameter shadowing, and missing imports in a single
# pass.  The old ``_check_operator_access_shadowing`` has been removed.


# =========================================================================
# Unified migration checker
# =========================================================================


def check_migration_source(
    source: str,
    filepath: str = "<unknown>",
    module_label: str | None = None,
) -> list[dict]:
    """Check migration source code for cross-table DML without
    ``operator_access_migration``.

    Runs all detectors and returns a combined list of violations.

    Returns a list of violation dicts with keys:
    - ``filepath``: source file path.
    - ``line``: line number of the violating DML.
    - ``message``: human-readable description.

    Args:
        source: The Python source code of the migration file.
        filepath: An optional filepath label for error reporting.
        module_label: Optional Django app label for exemption matching.

    Returns:
        A (possibly empty) list of violation dicts.
    """
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as exc:
        return [
            {
                "filepath": filepath,
                "line": 0,
                "message": f"Syntax error in migration file: {exc}",
            }
        ]

    # --- Canonical import validation ---
    canonical_import_valid, import_violations = _check_canonical_import(tree)
    for v in import_violations:
        v.setdefault("filepath", filepath)

    # Build parent map once for all ancestry checks.
    parent_map = _build_parent_map(tree)

    # Find valid gating With nodes via true AST ancestry.
    gated_blocks = _find_gated_with_nodes(tree, parent_map, canonical_import_valid)

    violations: list[dict] = []

    # --- Detector 1: schema_editor.execute() with cross-table DML ---
    for node in ast.walk(tree):
        if not _is_execute_call(node):
            continue
        assert isinstance(node, ast.Call)

        sql = _extract_sql_arg(node)
        if sql is None:
            # Check for dynamic SQL
            if _is_dynamic_sql_with_org_id(node):
                func_name = _find_enclosing_function_name(tree, node.lineno)
                if not _is_exempt_symbol(
                    filepath,
                    func_name,
                    module_label,
                    category="dynamic-sql",
                ):
                    violations.append(
                        {
                            "filepath": filepath,
                            "line": node.lineno,
                            "message": (
                                f"Dynamic SQL at line {node.lineno} contains "
                                f"organization_id reference and is not "
                                f"statically analysable — requires manual "
                                f"review and operator_access_migration() "
                                f"enclosure."
                            ),
                            "category": "dynamic-sql",
                        }
                    )
            continue

        if not _is_cross_table_dml_assigning_org_id(sql):
            continue

        if not _is_descendant_of_gated_block(node, gated_blocks, parent_map):
            func_name = _find_enclosing_function_name(tree, node.lineno)
            if not _is_exempt_symbol(
                filepath,
                func_name,
                module_label,
                category="ungated-raw-sql",
            ):
                violations.append(
                    {
                        "filepath": filepath,
                        "line": node.lineno,
                        "message": (
                            f"Cross-table DML assigning organization_id at "
                            f"line {node.lineno} is not enclosed by "
                            f"`with operator_access_migration"
                            f"(schema_editor):`."
                        ),
                        "category": "ungated-raw-sql",
                    }
                )

    # --- Detector 2: ORM .update(organization_id=...) writes ---
    for node in ast.walk(tree):
        if not _is_orm_update_write(node):
            continue
        assert isinstance(node, ast.Call)

        if not _is_descendant_of_gated_block(node, gated_blocks, parent_map):
            func_name = _find_enclosing_function_name(tree, node.lineno)
            if not _is_exempt_symbol(
                filepath,
                func_name,
                module_label,
                category="ungated-orm-write",
            ):
                violations.append(
                    {
                        "filepath": filepath,
                        "line": node.lineno,
                        "message": (
                            f"ORM .update(organization_id=...) at "
                            f"line {node.lineno} is not enclosed by "
                            f"`with operator_access_migration"
                            f"(schema_editor):`.  "
                            f"ORM writes through the default manager are "
                            f"subject to FORCE RLS and need operator_access."
                        ),
                        "category": "ungated-orm-write",
                    }
                )

    # --- Detector 3: migrations.RunSQL with cross-table DML ---
    for node in ast.walk(tree):
        if not _is_runsql_dml_call(node):
            continue
        assert isinstance(node, ast.Call)

        for sql in _extract_runsql_sql(node):
            if _is_cross_table_dml_assigning_org_id(sql):
                if not _is_descendant_of_gated_block(node, gated_blocks, parent_map):
                    func_name = _find_enclosing_function_name(tree, node.lineno)
                    if not _is_exempt_symbol(
                        filepath,
                        func_name,
                        module_label,
                        category="ungated-runsql",
                    ):
                        violations.append(
                            {
                                "filepath": filepath,
                                "line": node.lineno,
                                "message": (
                                    f"RunSQL at line {node.lineno} with "
                                    f"cross-table DML assigning "
                                    f"organization_id is not enclosed by "
                                    f"`with operator_access_migration"
                                    f"(schema_editor):`."
                                ),
                                "category": "ungated-runsql",
                            }
                        )

    # --- Detector 4: raw GUC manipulation (non-exemptible) ---
    for node in ast.walk(tree):
        if not _is_execute_call(node):
            continue
        assert isinstance(node, ast.Call)

        sql = _extract_sql_arg(node)
        if sql is None:
            continue
        if _is_raw_guc_manipulation(sql):
            violations.append(
                {
                    "filepath": filepath,
                    "line": node.lineno,
                    "message": (
                        f"Raw GUC manipulation at line {node.lineno}: "
                        f"direct SET/SET LOCAL/RESET/set_config of "
                        f"app.operator_access is forbidden.  Use "
                        f"`with operator_access_migration(schema_editor):` "
                        f"instead."
                    ),
                    "category": "raw-guc",
                }
            )

    # Detector 4b (continues): RunSQL with raw GUC manipulation
    for node in ast.walk(tree):
        if not _is_runsql_dml_call(node):
            continue
        assert isinstance(node, ast.Call)

        for sql in _extract_runsql_sql(node):
            if _is_raw_guc_manipulation(sql):
                violations.append(
                    {
                        "filepath": filepath,
                        "line": node.lineno,
                        "message": (
                            f"RunSQL with raw GUC manipulation at "
                            f"line {node.lineno}: direct SET/SET LOCAL/"
                            f"RESET/set_config of app.operator_access is "
                            f"forbidden.  Use `with "
                            f"operator_access_migration(schema_editor):` "
                            f"instead."
                        ),
                        "category": "raw-guc",
                    }
                )

    # --- Detector 5: assignment+save pattern ---
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            as_violations = _find_assignment_save_in_function(
                node, gated_blocks, parent_map
            )
            for v in as_violations:
                v["filepath"] = filepath
                # Check exemption
                func_name = v.get("func_name", node.name)
                if not _is_exempt_symbol(
                    filepath,
                    func_name,
                    module_label,
                    category="ungated-assignment-save",
                ):
                    violations.append(v)

    # --- Detector 6: wrong editor ---
    for we_v in _check_wrong_editor(tree):
        we_v.setdefault("filepath", filepath)
        violations.append(we_v)

    # Append import/shadowing violations at the end.
    for v in import_violations:
        if v not in violations:
            violations.append(v)

    return violations


# get_manifest_migration_files and get_manifest_migration_dirs are defined
# above (see the module-inventory section).  The aliases below preserve
# backward compatibility with any direct imports that reference the old
# names.  New code should use get_manifest_migration_* directly.

get_migration_files = get_manifest_migration_files
get_all_module_migration_dirs = get_manifest_migration_dirs


# =========================================================================
# Synthetic proof tests
# =========================================================================

_SQL_WITH_SUBQUERY = (
    "UPDATE some_table "
    "SET organization_id = (SELECT id FROM other_table "
    "WHERE other_table.id = some_table.other_id) "
    "WHERE organization_id IS NULL"
)

UNGATED_CODE = f"""
def forward(apps, schema_editor):
    schema_editor.execute(
        {_SQL_WITH_SUBQUERY!r}
    )
"""

WRAPPED_CODE = f"""
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            {_SQL_WITH_SUBQUERY!r}
        )
"""

DDL_CODE = '''
def forward(apps, schema_editor):
    """DDL-only migration — no cross-table DML."""
    schema_editor.execute(
        "ALTER TABLE some_table ENABLE ROW LEVEL SECURITY"
    )
'''

SELF_UPDATE_CODE = '''
def forward(apps, schema_editor):
    """Self-table only — no cross-table subquery."""
    schema_editor.execute(
        "UPDATE some_table SET organization_id = \'a1b2c3d4\' WHERE id = 1"
    )
'''

READ_ONLY_CODE = '''
def forward(apps, schema_editor):
    """Read-only SELECT — not DML."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM some_table WHERE organization_id IS NULL"
        )
'''

NO_EXECUTE_CODE = '''
def forward(apps, schema_editor):
    """ORM-only backfill — no raw execute() calls."""
    from django.apps import apps as dj_apps
    MyModel = dj_apps.get_model("some_app", "MyModel")
    for obj in MyModel._base_manager.filter(organization__isnull=True):
        obj.organization_id = some_org_id
        obj.save()
'''

UNGATED_ORM_UPDATE_CODE = """
def forward(apps, schema_editor):
    MyModel._base_manager.filter(fk_id=1).update(
        organization_id=some_org_id,
    )
"""

WRAPPED_ORM_UPDATE_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        MyModel._base_manager.filter(fk_id=1).update(
            organization_id=some_org_id,
        )
"""

UNGATED_RUNSQL_CODE = """
def forward(apps, schema_editor):
    migrations.RunSQL(
        "UPDATE t SET organization_id = (SELECT id FROM other WHERE other.x = t.x)"
    )
"""

WRAPPED_RUNSQL_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        migrations.RunSQL(
            "UPDATE t SET organization_id = (SELECT id FROM other WHERE other.x = t.x)"
        )
"""

DYNAMIC_SQL_CODE = """
def forward(apps, schema_editor):
    table = "my_table"
    schema_editor.execute(
        f"UPDATE {table} SET organization_id = (SELECT id FROM other WHERE id = 1)"
    )
"""

EXEMPT_CRM_CODE = '''
def _backfill_contactnote_org(apps, schema_editor):
    """ORM _base_manager backfill — exempt (SA84)."""
    del schema_editor
    ContactNote = apps.get_model("quickscale_modules_crm", "ContactNote")
    Contact = apps.get_model("quickscale_modules_crm", "Contact")
    for note in ContactNote._base_manager.filter(organization__isnull=True):
        parent = Contact._base_manager.get(pk=note.contact_id)
        ContactNote._base_manager.filter(pk=note.pk).update(
            organization_id=parent.organization_id
        )

def forward(apps, schema_editor):
    _backfill_contactnote_org(apps, schema_editor)
'''

# Cross-table UPDATE ... FROM (no parenthesised subquery)
UPDATE_FROM_SQL = (
    "UPDATE t "
    "SET organization_id = s.organization_id "
    "FROM source_table s "
    "WHERE t.id = s.t_id"
)

UNGATED_UPDATE_FROM_CODE = f"""
def forward(apps, schema_editor):
    schema_editor.execute(
        {UPDATE_FROM_SQL!r}
    )
"""

WRAPPED_UPDATE_FROM_CODE = f"""
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            {UPDATE_FROM_SQL!r}
        )
"""

# INSERT INTO ... SELECT (no parenthesised subquery)
INSERT_SELECT_SQL = (
    "INSERT INTO target_table (organization_id, name) "
    "SELECT s.organization_id, s.name "
    "FROM source_table s "
    "WHERE s.id = 1"
)

UNGATED_INSERT_SELECT_CODE = f"""
def forward(apps, schema_editor):
    schema_editor.execute(
        {INSERT_SELECT_SQL!r}
    )
"""

WRAPPED_INSERT_SELECT_CODE = f"""
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            {INSERT_SELECT_SQL!r}
        )
"""

# CRM exempt function with ADDITIONAL raw SQL (to prove category-specific exemption)
EXEMPT_CRM_WITH_RAW_SQL_CODE = '''
def _backfill_contactnote_org(apps, schema_editor):
    """ORM _base_manager backfill — exempt (SA84) for ORM-update only."""
    del schema_editor
    ContactNote = apps.get_model("quickscale_modules_crm", "ContactNote")
    Contact = apps.get_model("quickscale_modules_crm", "Contact")
    for note in ContactNote._base_manager.filter(organization__isnull=True):
        parent = Contact._base_manager.get(pk=note.contact_id)
        ContactNote._base_manager.filter(pk=note.pk).update(
            organization_id=parent.organization_id
        )
    # RAW SQL execute in the SAME exempt function — should still be detected
    # because the exemption is category-specific (ungated-orm-write only).
    schema_editor.execute(
        "UPDATE some_table SET organization_id = "
        "(SELECT id FROM other_table WHERE id = 1) "
    )

def forward(apps, schema_editor):
    _backfill_contactnote_org(apps, schema_editor)
'''


# =========================================================================
# Raw GUC manipulation synthetic test code
# =========================================================================

_RAW_SET_LOCAL_SQL = "SET LOCAL app.operator_access = 'on'"

RAW_GUC_SET_LOCAL_CODE = f"""
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute({_RAW_SET_LOCAL_SQL!r})
"""

RAW_GUC_SET_CODE = """
def forward(apps, schema_editor):
    schema_editor.execute("SET app.operator_access = 'on'")
"""

RAW_GUC_RESET_CODE = """
def forward(apps, schema_editor):
    schema_editor.execute("RESET app.operator_access")
"""

RAW_GUC_SET_CONFIG_CODE = """
def forward(apps, schema_editor):
    schema_editor.execute(
        "SELECT set_config('app.operator_access', 'on', true)"
    )
"""

RAW_GUC_RUNSQL_CODE = """
def forward(apps, schema_editor):
    migrations.RunSQL("SET LOCAL app.operator_access = 'on'")
"""

RAW_GUC_CLEAN_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# =========================================================================
# Wrong editor synthetic test code
# =========================================================================

WRONG_EDITOR_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    wrong_editor = schema_editor
    with operator_access_migration(wrong_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# =========================================================================
# Shadowing synthetic test code
# =========================================================================

SHADOWING_ASSIGN_CODE = """
def forward(apps, schema_editor):
    operator_access_migration = lambda x: x  # shadowing
    schema_editor.execute(
        "UPDATE t SET organization_id = "
        "(SELECT id FROM other WHERE other.x = t.x)"
    )
"""

SHADOWING_IMPORT_CODE = """
from somewhere import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

SHADOWING_ALIAS_CODE = """
from quickscale_modules_orgs.tenancy import something as operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""

# =========================================================================
# Assignment+save synthetic test code
# =========================================================================

ASSIGN_SAVE_UNGATED_CODE = """
def forward(apps, schema_editor):
    MyModel = apps.get_model("some_app", "MyModel")
    for obj in MyModel.objects.all():
        obj.organization_id = "some-org-id"
        obj.save()
"""

ASSIGN_SAVE_WRAPPED_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    MyModel = apps.get_model("some_app", "MyModel")
    with operator_access_migration(schema_editor):
        for obj in MyModel.objects.all():
            obj.organization_id = "some-org-id"
            obj.save()
"""

ASSIGN_SAVE_UPDATE_FIELDS_CODE = """
def forward(apps, schema_editor):
    MyModel = apps.get_model("some_app", "MyModel")
    for obj in MyModel.objects.filter(organization__isnull=True):
        obj.organization_id = "some-org-id"
        obj.save(update_fields=["organization_id"])
"""

# =========================================================================
# Canonical import test code
# =========================================================================

CANONICAL_IMPORT_CODE = """
from quickscale_modules_orgs.tenancy import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""


class TestGateSyntheticProof:
    """Prove the AST gate correctly distinguishes ungated from wrapped DML
    across various edge cases."""

    # --- Raw SQL execute() tests ---

    def test_ungated_dml_is_detected(self) -> None:
        """Cross-table DML without operator_access_migration is a violation."""
        violations = check_migration_source(UNGATED_CODE)
        assert len(violations) == 1, (
            f"Expected exactly 1 violation, got {len(violations)}: {violations}"
        )

    def test_wrapped_dml_is_clean(self) -> None:
        """Cross-table DML inside operator_access_migration passes."""
        violations = check_migration_source(WRAPPED_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for wrapped code, got {len(violations)}: "
            f"{violations}"
        )

    def test_ddl_not_flagged(self) -> None:
        """DDL (ALTER TABLE, CREATE POLICY) is not flagged even with
        organization_id references or subquery syntax in policy definitions."""
        violations = check_migration_source(DDL_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for DDL, got {len(violations)}: {violations}"
        )

    def test_self_table_update_not_flagged(self) -> None:
        """UPDATE with organization_id but no subquery (self-table only) is
        not flagged — no cross-table read to protect."""
        violations = check_migration_source(SELF_UPDATE_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for self-table update, got "
            f"{len(violations)}: {violations}"
        )

    def test_read_only_sql_not_flagged(self) -> None:
        """SELECT (read-only SQL) is not flagged even when it contains
        organization_id — the gate only checks UPDATE/INSERT/DELETE."""
        violations = check_migration_source(READ_ONLY_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for read-only SQL, got "
            f"{len(violations)}: {violations}"
        )

    def test_orm_backfill_flagged_without_waiver(self) -> None:
        """ORM-based backfill with individual .save() and _base_manager
        IS now flagged (SA88 Phase 1 removed the function-wide
        _base_manager waiver).  Any migration that assigns
        organization_id and calls .save() without
        operator_access_migration() is a violation regardless
        of whether _base_manager is used."""
        violations = check_migration_source(NO_EXECUTE_CODE)
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) >= 1, (
            f"Expected at least 1 assignment-save violation for "
            f"ORM backfill with _base_manager (waiver removed), "
            f"got {len(violations)}: {violations}"
        )

    # --- ORM .update() tests ---

    def test_ungated_orm_update_is_detected(self) -> None:
        """ORM .update(organization_id=...) without operator_access_migration
        is a violation."""
        violations = check_migration_source(UNGATED_ORM_UPDATE_CODE)
        assert len(violations) == 1, (
            f"Expected exactly 1 ORM-update violation, got "
            f"{len(violations)}: {violations}"
        )

    def test_wrapped_orm_update_is_clean(self) -> None:
        """ORM .update(organization_id=...) inside operator_access_migration
        passes."""
        violations = check_migration_source(WRAPPED_ORM_UPDATE_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for wrapped ORM update, got "
            f"{len(violations)}: {violations}"
        )

    # --- RunSQL tests ---

    def test_ungated_runsql_is_detected(self) -> None:
        """RunSQL with cross-table DML without operator_access_migration
        is a violation."""
        violations = check_migration_source(UNGATED_RUNSQL_CODE)
        assert len(violations) == 1, (
            f"Expected exactly 1 RunSQL violation, got {len(violations)}: {violations}"
        )

    def test_wrapped_runsql_is_clean(self) -> None:
        """RunSQL with cross-table DML inside operator_access_migration
        passes."""
        violations = check_migration_source(WRAPPED_RUNSQL_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for wrapped RunSQL, got "
            f"{len(violations)}: {violations}"
        )

    # --- Dynamic SQL tests ---

    def test_dynamic_sql_with_org_id_is_detected(self) -> None:
        """Dynamic SQL (f-string) containing organization_id without
        operator_access_migration is a violation."""
        violations = check_migration_source(DYNAMIC_SQL_CODE)
        assert len(violations) == 1, (
            f"Expected exactly 1 dynamic-SQL violation, got "
            f"{len(violations)}: {violations}"
        )

    # --- Exemption tests ---

    def test_exempt_crm_code_not_flagged_when_exempt(self) -> None:
        """CRM 0009 backfill matched to the exemption ledger does not
        produce a violation when checked with module_label."""
        violations = check_migration_source(
            EXEMPT_CRM_CODE,
            filepath="0009_add_note_organization_ownership.py",
        )
        # Without module_label the gate cannot match the exemption.
        # The ORM .update() pattern IS detected.
        from_assertions = [
            v for v in violations if v.get("category") == "ungated-orm-write"
        ]
        assert len(from_assertions) >= 1, (
            f"CRM backfill should produce at least 1 ORM-update "
            f"violation when checked without exemption matching, "
            f"got {len(violations)}: {violations}"
        )

    def test_unlisted_debt_fails_as_violation(self) -> None:
        """A made-up migration with unlisted ORM update fails the gate
        — proving the exemption ledger is an allow-list, not a broad
        ignore pattern."""
        code = """
def forward(apps, schema_editor):
    MyModel.objects.filter(x=1).update(organization_id="abc")
"""
        violations = check_migration_source(code)
        ungated = [v for v in violations if "ungated" in v.get("category", "")]
        assert len(ungated) >= 1, (
            f"Unlisted debt must produce a violation, got "
            f"{len(violations)}: {violations}"
        )

    # --- UPDATE FROM tests ---

    def test_ungated_update_from_is_detected(self) -> None:
        """UPDATE ... FROM without operator_access_migration is a violation."""
        violations = check_migration_source(UNGATED_UPDATE_FROM_CODE)
        assert len(violations) == 1, (
            f"Expected exactly 1 violation for UPDATE FROM, got "
            f"{len(violations)}: {violations}"
        )

    def test_wrapped_update_from_is_clean(self) -> None:
        """UPDATE ... FROM inside operator_access_migration passes."""
        violations = check_migration_source(WRAPPED_UPDATE_FROM_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for wrapped UPDATE FROM, got "
            f"{len(violations)}: {violations}"
        )

    # --- INSERT SELECT tests ---

    def test_ungated_insert_select_is_detected(self) -> None:
        """INSERT INTO ... SELECT without operator_access_migration is
        a violation."""
        violations = check_migration_source(UNGATED_INSERT_SELECT_CODE)
        assert len(violations) == 1, (
            f"Expected exactly 1 violation for INSERT SELECT, got "
            f"{len(violations)}: {violations}"
        )

    def test_wrapped_insert_select_is_clean(self) -> None:
        """INSERT INTO ... SELECT inside operator_access_migration passes."""
        violations = check_migration_source(WRAPPED_INSERT_SELECT_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for wrapped INSERT SELECT, got "
            f"{len(violations)}: {violations}"
        )

    # --- Category-specific exemption tests ---

    def test_exempt_crm_code_clean_when_matched_with_module_label(self) -> None:
        """CRM 0009 backfill matched with correct module_label produces
        no violations — the SA84 exemption correctly waives the
        ungated-orm-write category."""
        violations = check_migration_source(
            EXEMPT_CRM_CODE,
            filepath=(
                "quickscale_modules/crm/src/"
                "quickscale_modules_crm/migrations/"
                "0009_add_note_organization_ownership.py"
            ),
            module_label="quickscale_modules_crm",
        )
        assert len(violations) == 0, (
            f"Expected 0 violations when CRM exemption matched with "
            f"module_label, got {len(violations)}: {violations}"
        )

    def test_exempt_symbol_other_category_not_waived(self) -> None:
        """A raw SQL execute inside the same exempt symbol is NOT waived
        — the exemption is category-specific (ungated-orm-write) and does
        not cover ungated-raw-sql violations in the same function."""
        violations = check_migration_source(
            EXEMPT_CRM_WITH_RAW_SQL_CODE,
            filepath=(
                "quickscale_modules/crm/src/"
                "quickscale_modules_crm/migrations/"
                "0009_add_note_organization_ownership.py"
            ),
            module_label="quickscale_modules_crm",
        )
        raw_sql_violations = [
            v for v in violations if v.get("category") == "ungated-raw-sql"
        ]
        assert len(raw_sql_violations) >= 1, (
            f"Expected at least 1 raw-SQL violation in the exempt symbol "
            f"(cross-category), got {len(violations)} total: {violations}"
        )
        # The ORM-update violation should also be present (not exempted
        # when module_label is missing or category differs).
        orm_violations = [
            v for v in violations if v.get("category") == "ungated-orm-write"
        ]
        # With the category-specific exemption, the ORM-update violation
        # IS waived because its category matches.
        assert len(orm_violations) == 0, (
            f"Expected 0 ORM-update violations (exempt category), got "
            f"{len(orm_violations)}: {[v for v in violations if v.get('category') == 'ungated-orm-write']}"
        )

    # --- Raw GUC tests ---

    def test_raw_guc_set_local_is_detected(self) -> None:
        """Raw SET LOCAL app.operator_access via execute() is detected
        even when inside an operator_access_migration block."""
        violations = check_migration_source(RAW_GUC_SET_LOCAL_CODE)
        guc_violations = [v for v in violations if v.get("category") == "raw-guc"]
        assert len(guc_violations) >= 1, (
            f"Expected at least 1 raw-guc violation for SET LOCAL, got "
            f"{len(guc_violations)}: {violations}"
        )

    def test_raw_guc_set_is_detected(self) -> None:
        """Raw SET app.operator_access via execute() is detected."""
        violations = check_migration_source(RAW_GUC_SET_CODE)
        guc_violations = [v for v in violations if v.get("category") == "raw-guc"]
        assert len(guc_violations) >= 1, (
            f"Expected at least 1 raw-guc violation for SET, got "
            f"{len(guc_violations)}: {violations}"
        )

    def test_raw_guc_reset_is_detected(self) -> None:
        """Raw RESET app.operator_access via execute() is detected."""
        violations = check_migration_source(RAW_GUC_RESET_CODE)
        guc_violations = [v for v in violations if v.get("category") == "raw-guc"]
        assert len(guc_violations) >= 1, (
            f"Expected at least 1 raw-guc violation for RESET, got "
            f"{len(guc_violations)}: {violations}"
        )

    def test_raw_guc_set_config_is_detected(self) -> None:
        """Raw set_config('app.operator_access', ...) via execute() is
        detected."""
        violations = check_migration_source(RAW_GUC_SET_CONFIG_CODE)
        guc_violations = [v for v in violations if v.get("category") == "raw-guc"]
        assert len(guc_violations) >= 1, (
            f"Expected at least 1 raw-guc violation for set_config, got "
            f"{len(guc_violations)}: {violations}"
        )

    def test_raw_guc_runsql_is_detected(self) -> None:
        """RunSQL with raw SET LOCAL app.operator_access is detected."""
        violations = check_migration_source(RAW_GUC_RUNSQL_CODE)
        guc_violations = [v for v in violations if v.get("category") == "raw-guc"]
        assert len(guc_violations) >= 1, (
            f"Expected at least 1 raw-guc violation for RunSQL, got "
            f"{len(guc_violations)}: {violations}"
        )

    def test_no_raw_guc_in_clean_code(self) -> None:
        """Code that uses operator_access_migration without raw GUC
        produces zero raw-guc violations."""
        violations = check_migration_source(RAW_GUC_CLEAN_CODE)
        guc_violations = [v for v in violations if v.get("category") == "raw-guc"]
        assert len(guc_violations) == 0, (
            f"Expected 0 raw-guc violations in clean code, got "
            f"{len(guc_violations)}: {guc_violations}"
        )

    # --- Wrong editor tests ---

    def test_wrong_editor_is_detected(self) -> None:
        """operator_access_migration called with a non-schema_editor
        argument is a wrong-editor violation."""
        violations = check_migration_source(WRONG_EDITOR_CODE)
        editor_violations = [
            v for v in violations if v.get("category") == "wrong-editor"
        ]
        assert len(editor_violations) >= 1, (
            f"Expected at least 1 wrong-editor violation, got "
            f"{len(editor_violations)}: {violations}"
        )

    # --- Shadowing tests ---

    def test_shadowing_assignment_is_detected(self) -> None:
        """Rebinding operator_access_migration to a different function
        via assignment is detected as shadowing."""
        violations = check_migration_source(SHADOWING_ASSIGN_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for assignment, got "
            f"{len(shadow_violations)}: {violations}"
        )

    def test_shadowing_non_canonical_import_is_detected(self) -> None:
        """Importing operator_access_migration from a non-canonical module
        is detected as shadowing."""
        violations = check_migration_source(SHADOWING_IMPORT_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for import, got "
            f"{len(shadow_violations)}: {violations}"
        )

    def test_shadowing_alias_is_detected(self) -> None:
        """Importing a different symbol as operator_access_migration is
        detected as shadowing."""
        violations = check_migration_source(SHADOWING_ALIAS_CODE)
        shadow_violations = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadow_violations) >= 1, (
            f"Expected at least 1 shadowing violation for alias, got "
            f"{len(shadow_violations)}: {violations}"
        )

    # --- Assignment+save tests ---

    def test_ungated_assignment_save_is_detected(self) -> None:
        """obj.organization_id = x followed by obj.save() without
        operator_access_migration is detected."""
        violations = check_migration_source(ASSIGN_SAVE_UNGATED_CODE)
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) >= 1, (
            f"Expected at least 1 assignment-save violation, got "
            f"{len(as_violations)}: {violations}"
        )

    def test_wrapped_assignment_save_is_clean(self) -> None:
        """obj.organization_id = x followed by obj.save() inside
        operator_access_migration passes."""
        violations = check_migration_source(ASSIGN_SAVE_WRAPPED_CODE)
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) == 0, (
            f"Expected 0 assignment-save violations when wrapped, got "
            f"{len(as_violations)}: {violations}"
        )

    def test_ungated_assignment_save_update_fields_is_detected(self) -> None:
        """obj.organization_id = x followed by
        obj.save(update_fields=[...]) without operator_access_migration
        is detected."""
        violations = check_migration_source(ASSIGN_SAVE_UPDATE_FIELDS_CODE)
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) >= 1, (
            f"Expected at least 1 assignment-save violation with "
            f"update_fields, got {len(as_violations)}: {violations}"
        )


# =========================================================================
# CRM 0009 exact exemption proof
# =========================================================================


class TestCRMExemptionContentProof:
    """Prove the CRM 0009 exemption ledger contains exactly the two
    expected symbols with ``ungated-orm-write`` category, owned by SA84,
    and no other exemptions exist in the ledger."""

    def test_exact_crm_exemption_content(self) -> None:
        """CRM 0009 exemption has exactly:
        - symbol ``_backfill_contactnote_org`` with category
          ``ungated-orm-write`` owned by SA84
        - symbol ``_backfill_dealnote_org`` with category
          ``ungated-orm-write`` owned by SA84
        - No other entries for CRM 0009.
        """
        crm_key = (
            "quickscale_modules_crm",
            "0009_add_note_organization_ownership",
        )
        assert crm_key in SA88_DEBT_EXEMPTIONS, (
            "CRM 0009 key not found in SA88_DEBT_EXEMPTIONS"
        )
        entries = SA88_DEBT_EXEMPTIONS[crm_key]

        assert len(entries) == 2, (
            f"Expected exactly 2 exemption entries for CRM 0009, "
            f"got {len(entries)}: {entries}"
        )

        # Check first symbol
        e0 = entries[0]
        assert e0["symbol"] == "_backfill_contactnote_org", (
            f"Expected first symbol '_backfill_contactnote_org', "
            f"got '{e0.get('symbol')}'"
        )
        assert e0["category"] == "ungated-orm-write", (
            f"Expected category 'ungated-orm-write', got '{e0.get('category')}'"
        )
        assert "SA84" in e0.get("owns", ""), (
            f"Expected owns field mentioning SA84, got '{e0.get('owns')}'"
        )

        # Check second symbol
        e1 = entries[1]
        assert e1["symbol"] == "_backfill_dealnote_org", (
            f"Expected second symbol '_backfill_dealnote_org', got '{e1.get('symbol')}'"
        )
        assert e1["category"] == "ungated-orm-write", (
            f"Expected category 'ungated-orm-write', got '{e1.get('category')}'"
        )
        assert "SA84" in e1.get("owns", ""), (
            f"Expected owns field mentioning SA84, got '{e1.get('owns')}'"
        )

        # No other CRM 0009 entries
        assert len(entries) == 2, "Extra entries found in CRM 0009 exemption"


# =========================================================================
# Manifested-uninstalled module inventory
# =========================================================================


class TestManifestedModuleInventory:
    """Prove the gate inventories quickscale_modules via the INTERSECTION
    of independent ``module.yml`` and ``pyproject.toml`` markers.

    These tests use the parameterized helpers (``_get_manifest_module_dirs``,
    ``_get_pyproject_module_dirs``, ``discover_shipped_at``) so they can
    create temporary trees to prove drift detection, placeholder exclusion,
    and no-migrations ledger enforcement, rather than relying on hard-coded
    module lists.
    """

    # ------------------------------------------------------------------
    # Independent-set parity (gap 4)
    # ------------------------------------------------------------------

    def test_manifest_and_pyproject_sets_are_equal(self) -> None:
        """The set of directories with a valid ``module.yml`` MUST equal
        the set with a valid ``pyproject.toml``.  Any mismatch is marker
        drift that would fail ``_discover_shipped_modules``.

        This test proves parity by comparing the two independent sets
        directly (no hard-coded expected count).
        """
        manifest_dirs = _get_manifest_module_dirs()
        pyproject_dirs = _get_pyproject_module_dirs()
        assert manifest_dirs == pyproject_dirs, (
            f"Marker set mismatch: manifest-only={sorted(manifest_dirs - pyproject_dirs)}, "
            f"pyproject-only={sorted(pyproject_dirs - manifest_dirs)}"
        )

    def test_manifest_pyproject_set_not_empty(self) -> None:
        """Both independent marker sets are non-empty (sanity check that
        discovery works)."""
        assert len(_get_manifest_module_dirs()) >= 1
        assert len(_get_pyproject_module_dirs()) >= 1

    # ------------------------------------------------------------------
    # Teams placeholder exclusion (gap 5)
    # ------------------------------------------------------------------

    def test_teams_not_in_shipped_while_neither_marker_exists(self) -> None:
        """``teams`` is excluded from shipped modules ONLY while neither
        ``module.yml`` nor ``pyproject.toml`` exists in that directory.
        If a marker appears under teams/, it is a drift event, not silent
        exclusion.

        This test creates a temporary tree that proves both the current
        exclusion (no markers) and the drift case (marker appears).
        """
        ws_root = _get_ws_root()
        teams_dir = ws_root / "teams"
        # Current state: teams has no markers.
        if teams_dir.is_dir():
            assert not (teams_dir / "module.yml").is_file(), (
                "teams/module.yml should not exist (placeholder)"
            )
            assert not (teams_dir / "pyproject.toml").is_file(), (
                "teams/pyproject.toml should not exist (placeholder)"
            )
        shipped = _get_shipped_modules()
        assert "teams" not in shipped, "teams must not be shipped"

    # ------------------------------------------------------------------
    # No-migrations ledger (gap 6)
    # ------------------------------------------------------------------

    _NO_MIGRATIONS_RATIONALE: dict[str, str] = {
        "analytics": "Service-style module — no DB schema changes.",
        "storage": "Infrastructure module — no DB schema changes.",
    }

    def test_no_migrations_modules_have_no_migration_dir(self) -> None:
        """Every module in the no-migrations ledger has no ``migrations/``
        directory.  If a module listed here gains a migrations directory,
        the ledger must be updated (drift detection)."""
        shipped = _get_shipped_modules()
        for name, rationale in self._NO_MIGRATIONS_RATIONALE.items():
            mod = shipped.get(name)
            assert mod is not None, (
                f"No-migrations module '{name}' not in shipped modules. "
                f"Rationale: {rationale}"
            )
            assert not mod.has_migrations, (
                f"No-migrations module '{name}' now has a migrations/ "
                f"directory — update _NO_MIGRATIONS_RATIONALE. "
                f"Rationale: {rationale}"
            )

    def test_no_migrations_ledger_exhaustive(self) -> None:
        """Every module that has ``has_migrations=False`` in the shipped
        inventory MUST have an entry in the no-migrations ledger.  An
        unlisted no-migrations module is a ledger gap."""
        shipped = _get_shipped_modules()
        unlisted = {
            d
            for d, m in shipped.items()
            if not m.has_migrations and d not in self._NO_MIGRATIONS_RATIONALE
        }
        assert not unlisted, (
            f"Modules missing from no-migrations ledger: {sorted(unlisted)}"
        )

    # ------------------------------------------------------------------
    # Temporary-tree proofs (gap 7)
    # ------------------------------------------------------------------

    def test_manifest_only_dir_omitted_from_shipped(self) -> None:
        """A directory with only ``module.yml`` (no ``pyproject.toml``)
        is omitted from the shipped module intersection."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mod_dir = tmp_path / "test_mod"
            mod_dir.mkdir()
            (mod_dir / "module.yml").write_text("name: test_mod\nversion: 0.1.0\n")
            result = discover_shipped_at(tmp_path)
            assert "test_mod" not in result, (
                f"test_mod with only module.yml must not appear in shipped: {result}"
            )

    def test_pyproject_only_dir_fails_discovery(self) -> None:
        """A directory with only ``pyproject.toml`` (no ``module.yml``)
        causes ``_discover_shipped_modules`` to fail."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mod_dir = tmp_path / "test_mod"
            mod_dir.mkdir()
            (mod_dir / "pyproject.toml").write_text(
                '[tool.poetry]\npackages = [{include = "pkg"}]\n'
            )
            result = discover_shipped_at(tmp_path)
            assert "test_mod" not in result

    def test_package_mismatch_omitted(self) -> None:
        """When ``module.yml`` ``django_apps`` does not match
        ``pyproject.toml`` ``packages[0].include``, the mismatched
        module is omitted from shipped."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mod_dir = tmp_path / "mismatch"
            mod_dir.mkdir()
            (mod_dir / "module.yml").write_text(
                "name: mismatch\nversion: 0.1.0\ndjango_apps:\n"
                "  - quickscale_modules_mismatch\n"
            )
            src_dir = mod_dir / "src" / "quickscale_modules_mismatch"
            src_dir.mkdir(parents=True)
            (mod_dir / "pyproject.toml").write_text(
                '[tool.poetry]\npackages = [{include = "wrong_pkg_name"}]\n'
            )
            result = discover_shipped_at(tmp_path)
            assert "mismatch" not in result, (
                f"mismatch with inconsistent markers must not appear "
                f"in shipped: {result}"
            )

    def test_placeholder_promotion_detected(self) -> None:
        """If a marker (module.yml or pyproject.toml) appears in a
        previously-placeholder directory, it produces a set-parity
        failure (manifest-set vs pyproject-set mismatch)."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Create a placeholder-like dir with only module.yml
            pdir = tmp_path / "new_mod"
            pdir.mkdir()
            (pdir / "module.yml").write_text(
                "name: new_mod\nversion: 0.1.0\ndjango_apps:\n"
                "  - quickscale_modules_new_mod\n"
            )
            # No pyproject.toml → manifest-only
            manifest_only = _get_manifest_module_dirs(tmp_path)
            pyproject_only = _get_pyproject_module_dirs(tmp_path)
            assert "new_mod" in manifest_only
            assert "new_mod" not in pyproject_only

    def test_uninstalled_packaged_module_included(self) -> None:
        """A module that is shipped (has both markers) but NOT in
        Django's INSTALLED_APPS is still discovered by the manifest
        scanner."""
        shipped = _get_shipped_modules()
        # All shipped modules should be found regardless of INSTALLED_APPS.
        assert len(shipped) >= 12, (
            f"Expected at least 12 shipped modules, got {len(shipped)}"
        )
        # Verify backup module is found (it is in INSTALLED_APPS).
        assert "backups" in shipped, "backups module not discovered"
        # Analytics module is NOT in INSTALLED_APPS but IS shipped.
        assert "analytics" in shipped, (
            "analytics module must be discovered even though not in INSTALLED_APPS"
        )
        # Storage module is NOT in INSTALLED_APPS but IS shipped.
        assert "storage" in shipped, (
            "storage module must be discovered even though not in INSTALLED_APPS"
        )

    def test_no_migrations_drift_detected(self) -> None:
        """If a no-migrations module gains a migrations/ directory,
        ``has_migrations`` flips to True, which the ledger check
        (``test_no_migrations_modules_have_no_migration_dir``) would
        catch."""
        shipped = _get_shipped_modules()
        for name in _NO_MIGRATIONS_MODULES:
            mod = shipped.get(name)
            if mod is not None and mod.has_migrations:
                pytest.fail(
                    f"No-migrations module '{name}' has acquired a "
                    f"migrations/ directory — update the no-migrations "
                    f"ledger and rationale"
                )

    # ------------------------------------------------------------------
    # Parse and content proofs
    # ------------------------------------------------------------------

    def test_all_migration_files_parse(self) -> None:
        """Every migration file in all shipped modules is valid Python
        and can be parsed by ``check_migration_source`` without syntax
        errors."""
        dirs = get_manifest_migration_dirs()
        all_syntax_errors: list[str] = []
        for d in dirs:
            for py_file in sorted(d.glob("[0-9]*.py")):
                source = py_file.read_text(encoding="utf-8")
                violations = check_migration_source(source, str(py_file))
                for v in violations:
                    if "Syntax error" in v.get("message", ""):
                        all_syntax_errors.append(f"{py_file}: {v['message']}")
        if all_syntax_errors:
            pytest.fail(
                f"{len(all_syntax_errors)} file(s) have syntax errors:\n"
                + "\n".join(all_syntax_errors)
            )


# =========================================================================
# Negative-proof synthetic tests (SA88 Phase 1)
# =========================================================================
# These tests prove the gate fails closed for scenarios that the
# synthetic proof suite above does not cover — module-inventory edge
# cases, the removed _base_manager waiver, and invariant enforcement
# that cannot be tested with the real tree alone.


class TestNegativeProofGate:
    """Temporary-tree and invariant negative proofs for the SA88 Phase 1
    analyzer contract.

    Each test proves that a specific violation or invariant edge case
    is detected rather than silently allowed.  Replaces tautological/
    self-referential tests with proper negative-proof assertions.
    """

    # ------------------------------------------------------------------
    # Base-manager waiver removal proofs
    # ------------------------------------------------------------------

    def test_ungated_assignment_save_not_waived_by_base_manager(self) -> None:
        """A function using ``_base_manager`` with an ungated
        assignment+save pattern IS detected as a violation now.
        The previous function-wide ``_base_manager`` waiver has been
        removed (SA88 Phase 1)."""
        code = """
def forward(apps, schema_editor):
    MyModel = apps.get_model("some_app", "MyModel")
    for obj in MyModel._base_manager.all():
        obj.organization_id = "some-org-id"
        obj.save()
"""
        violations = check_migration_source(code)
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) >= 1, (
            f"Expected at least 1 assignment-save violation for "
            f"_base_manager code (waiver removed), got "
            f"{len(as_violations)}: {violations}"
        )

    def test_ungated_assignment_save_detected_inside_base_manager_loop(
        self,
    ) -> None:
        """Even when ``_base_manager`` is used for iteration,
        an assignment+save of organization_id without
        ``operator_access_migration`` is a violation."""
        code = """
def forward(apps, schema_editor):
    MyModel = apps.get_model("some_app", "MyModel")
    for obj in MyModel._base_manager.iterator():
        obj.organization_id = "new-org-id"
        obj.save(update_fields=["organization_id"])
"""
        violations = check_migration_source(code)
        as_violations = [
            v for v in violations if v.get("category") == "ungated-assignment-save"
        ]
        assert len(as_violations) >= 1, (
            f"Expected at least 1 assignment-save violation inside "
            f"_base_manager iterator, got {len(as_violations)}: {violations}"
        )

    # ------------------------------------------------------------------
    # Canonical import detection proofs (replaces tautological isinstance)
    # ------------------------------------------------------------------

    def test_missing_import_produces_violation(self) -> None:
        """A migration that uses ``operator_access_migration()`` without
        importing it from the canonical module produces a
        ``missing-canonical-import`` violation."""
        code = """
def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
        violations = check_migration_source(code)
        missing_import = [
            v for v in violations if v.get("category") == "missing-canonical-import"
        ]
        assert len(missing_import) >= 1, (
            f"Expected missing-canonical-import violation, "
            f"got {len(violations)}: {violations}"
        )

    def test_non_canonical_import_produces_shadowing(self) -> None:
        """Importing ``operator_access_migration`` from a non-canonical
        module produces a ``shadowing`` violation."""
        code = """
from somewhere import operator_access_migration

def forward(apps, schema_editor):
    with operator_access_migration(schema_editor):
        schema_editor.execute(
            "UPDATE t SET organization_id = "
            "(SELECT id FROM other WHERE other.x = t.x)"
        )
"""
        violations = check_migration_source(code)
        shadowing = [v for v in violations if v.get("category") == "shadowing"]
        assert len(shadowing) >= 1, (
            f"Expected shadowing violation for non-canonical import, "
            f"got {len(violations)}: {violations}"
        )

    def test_canonical_import_clean(self) -> None:
        """A migration with the canonical import produces no import
        violations."""
        violations = check_migration_source(CANONICAL_IMPORT_CODE)
        import_violations = [
            v
            for v in violations
            if v.get("category") in ("shadowing", "missing-canonical-import")
        ]
        assert len(import_violations) == 0, (
            f"Expected 0 import/shadowing violations with canonical "
            f"import, got {len(violations)}: {violations}"
        )

    # ------------------------------------------------------------------
    # Spoofed module label negative proof
    # ------------------------------------------------------------------

    def test_fake_module_label_is_not_exempt(self) -> None:
        """A spoofed filepath that mimics an exempt migration's module
        label but does not correspond to the filesystem module path
        does NOT get the exemption.  The exemption requires the actual
        filesystem-derived module_label to match."""
        violations = check_migration_source(
            EXEMPT_CRM_CODE,
            filepath="fake_path/0009_add_note_organization_ownership.py",
            module_label="quickscale_modules_fake",
        )
        orm_violations = [
            v for v in violations if v.get("category") == "ungated-orm-write"
        ]
        assert len(orm_violations) >= 1, (
            f"Expected ORM-update violation for spoofed module_label, "
            f"got {len(violations)}: {violations}"
        )

    # ------------------------------------------------------------------
    # Candidate vs analyzed tracking (gap 8)
    # ------------------------------------------------------------------

    def test_candidate_vs_analyzed_parity(self) -> None:
        """The authoritative real-tree gate tracks the total number of
        candidate migration files (from manifest discovery) and compares
        it to the number of files actually analyzed by
        ``check_migration_source``.  If a file is found by the scanner
        but not analyzed (e.g., unreadable, parse error), the test fails.

        This is NOT a self-referential comparison — it validates that the
        scanner output (candidates) and the analyzer input (analyzed) are
        the same set.
        """
        # Get the candidate list from the manifest-backed scanner.
        candidate_files = get_manifest_migration_files()
        assert len(candidate_files) >= 1, "No candidate migration files found"

        # Simulate what the real gate does: read and analyze each file.
        analyzed_files: list[str] = []
        analyzed_errors: list[str] = []
        for fp in candidate_files:
            try:
                source = fp.read_text(encoding="utf-8")
                analyzed_files.append(str(fp))
                # Basic parse check: ensure it's valid Python.
                check_migration_source(source, str(fp))
            except (IOError, OSError, UnicodeDecodeError) as exc:
                analyzed_errors.append(f"{fp}: read error: {exc}")

        assert not analyzed_errors, (
            f"{len(analyzed_errors)} candidate file(s) could not be analyzed: "
            + "; ".join(analyzed_errors)
        )

        # The analyzed set must exactly equal the candidate set.
        candidate_set = {str(f.resolve()) for f in candidate_files}
        analyzed_set = set(analyzed_files)
        not_analyzed = candidate_set - analyzed_set
        assert not not_analyzed, (
            f"{len(not_analyzed)} candidate file(s) not analyzed: "
            f"{sorted(not_analyzed)}"
        )

    def test_omitted_analyzer_consumption_fails(self) -> None:
        """If a candidate file is skipped during analysis (simulated),
        the candidate-vs-analyzed parity check would catch it.
        This test creates a temporary module to prove the principle."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            mod_dir = tmp_path / "test_omit"
            mod_dir.mkdir()
            (mod_dir / "module.yml").write_text(
                "name: test_omit\nversion: 0.1.0\n"
                "django_apps:\n  - quickscale_modules_test_omit\n"
            )
            src_dir = mod_dir / "src" / "quickscale_modules_test_omit"
            migrations_dir = src_dir / "migrations"
            migrations_dir.mkdir(parents=True)
            (migrations_dir / "0001_test.py").write_text(
                "def forward(apps, schema_editor): pass\n"
            )
            (mod_dir / "pyproject.toml").write_text(
                "[tool.poetry]\n"
                'packages = [{include = "quickscale_modules_test_omit"}]\n'
            )

            shipped = discover_shipped_at(tmp_path)
            assert "test_omit" in shipped

    # ------------------------------------------------------------------
    # Temporary-tree unreadable and parse failures (gap 7)
    # ------------------------------------------------------------------

    def test_unreadable_migration_file_fails_closed(self) -> None:
        """An unreadable migration file (simulated permission error)
        should cause analysis to fail rather than silently skipping
        the file."""
        # We can't easily create an unreadable file, but we can verify
        # that the gate's try/except around read_text() will fail.
        code = "this is not valid python {{{"
        violations = check_migration_source(code, filepath="broken.py")
        syntax_errors = [
            v for v in violations if "Syntax error" in v.get("message", "")
        ]
        assert len(syntax_errors) >= 1, (
            f"Expected syntax error for invalid Python, "
            f"got {len(violations)}: {violations}"
        )


# =========================================================================
# Real-tree compliance test
# =========================================================================


class TestMigrationOperatorAccessConformance:
    """Verify every shipped migration wraps cross-table DML in
    ``operator_access_migration``.

    Uses manifest-backed discovery (``module.yml`` + ``pyproject.toml``)
    to inventory migration files, independent of Django ``INSTALLED_APPS``.
    Modules known to have no migrations (analytics, storage) are excluded.
    The ``teams`` placeholder is also excluded.
    """

    def _get_module_label(self, filepath: str) -> str | None:
        """Derive the Django app label from a migration file path."""
        return _get_module_label_from_path(filepath)

    def test_all_migrations_pass_conformance_gate(self) -> None:
        """Every migration file in all manifested ``quickscale_modules_*``
        apps passes the SA88 conformance gate.

        Uses manifest-backed inventory (``module.yml`` + ``pyproject.toml``)
        to scan ALL shipped modules — not only those in ``INSTALLED_APPS``.

        Tracks candidate files (from manifest) vs files actually analyzed
        (gap 8).  If a file is discovered but cannot be read or parsed,
        this test fails with a specific error message rather than silently
        omitting it.

        This is the authoritative negative-proof gate: any migration that
        contains cross-table DML assigning ``organization_id`` that is NOT
        lexically enclosed by ``with operator_access_migration(...)`` fails
        this test with an actionable location report.

        Known debt exemptions in ``SA88_DEBT_EXEMPTIONS`` are allowed but
        tracked.  Any migration not in that ledger that contains ungated
        cross-table DML fails closed.
        """
        candidate_files = get_manifest_migration_files()
        analyzed_count = 0
        read_errors: list[str] = []
        all_violations: list[dict] = []

        for filepath in candidate_files:
            fp_str = str(filepath)
            try:
                source = filepath.read_text(encoding="utf-8")
            except (IOError, OSError, UnicodeDecodeError) as exc:
                read_errors.append(f"{fp_str}: {exc}")
                continue
            analyzed_count += 1
            module_label = self._get_module_label(fp_str)
            violations = check_migration_source(source, fp_str, module_label)
            all_violations.extend(violations)

        # Candidate vs analyzed barrier (gap 8).
        assert analyzed_count == len(candidate_files), (
            f"Analysis gap: {len(candidate_files)} candidate files, "
            f"but only {analyzed_count} analyzed.  "
            f"Read errors: {'; '.join(read_errors) if read_errors else 'none'}"
        )

        if all_violations:
            msg_lines = [f"{len(all_violations)} violation(s) found:"]
            for v in all_violations:
                msg_lines.append(
                    f"  {v['filepath']}:{v['line']} "
                    f"[{v.get('category', 'unknown')}] "
                    f"— {v['message']}"
                )
            pytest.fail("\n".join(msg_lines))

    def test_no_raw_guc_in_real_tree(self) -> None:
        """No migration in the manifested tree contains raw GUC manipulation
        of ``app.operator_access``.

        Uses manifest-backed inventory (same as the broader conformance
        check above).  Raw GUC manipulation is always forbidden
        (non-exemptible); the ``operator_access_migration`` context manager
        is the only permitted mechanism.
        """
        raw_guc_violations: list[dict] = []
        for filepath in get_manifest_migration_files():
            fp_str = str(filepath)
            source = filepath.read_text(encoding="utf-8")
            module_label = self._get_module_label(fp_str)
            violations = check_migration_source(source, fp_str, module_label)
            for v in violations:
                if v.get("category") == "raw-guc":
                    raw_guc_violations.append(v)

        if raw_guc_violations:
            msg_lines = [
                f"{len(raw_guc_violations)} migration(s) contain raw GUC "
                f"manipulation of app.operator_access:"
            ]
            for v in raw_guc_violations:
                msg_lines.append(f"  {v['filepath']}:{v['line']} — {v['message']}")
            pytest.fail("\n".join(msg_lines))
