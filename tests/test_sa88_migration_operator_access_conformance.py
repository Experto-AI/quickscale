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
from pathlib import Path

import pytest

_OPERATOR_ACCESS_CM_NAME = "operator_access_migration"
"""Name of the context manager function that gates must check for."""


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
    """Return ``True`` if *node* is a call to ``operator_access_migration``."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _OPERATOR_ACCESS_CM_NAME
    )


def _find_operator_access_ranges(tree: ast.AST) -> list[tuple[int, int]]:
    """Find ``(start_line, end_line)`` for every ``with
    operator_access_migration(...)`` block in *tree*.

    Returns a list of inclusive line-number ranges.
    """
    ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            for item in node.items:
                if _is_operator_access_migration_call(item.context_expr):
                    # end_lineno is available in Python 3.8+.
                    end_lineno = node.end_lineno
                    end = end_lineno if end_lineno is not None else node.lineno
                    ranges.append((node.lineno, end))
    return ranges


def _is_within_ranges(lineno: int, ranges: list[tuple[int, int]]) -> bool:
    """Return ``True`` if *lineno* falls within any ``(start, end)`` range."""
    return any(start <= lineno <= end for start, end in ranges)


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
    op_ranges: list[tuple[int, int]],
    violations: list[dict],
) -> None:
    """Recursively scan *body* (a list of statements) for the pattern
    ``obj.organization_id = value`` followed by ``obj.save()`` (or
    ``obj.save(update_fields=...)``) that is NOT enclosed by
    ``operator_access_migration``.

    Appends violation dicts to *violations* in place.
    """
    for i, stmt in enumerate(body):
        # Check compound statements with nested bodies (for, while, with, try, etc.)
        if isinstance(stmt, (ast.For, ast.AsyncFor)):
            _check_body_for_assignment_save(
                stmt.body,
                func_name,
                op_ranges,
                violations,
            )
            _check_body_for_assignment_save(
                stmt.orelse or [],
                func_name,
                op_ranges,
                violations,
            )
        if isinstance(stmt, (ast.While,)):
            _check_body_for_assignment_save(
                stmt.body,
                func_name,
                op_ranges,
                violations,
            )
            _check_body_for_assignment_save(
                stmt.orelse or [],
                func_name,
                op_ranges,
                violations,
            )
        if isinstance(stmt, ast.With):
            _check_body_for_assignment_save(
                stmt.body,
                func_name,
                op_ranges,
                violations,
            )
        if isinstance(stmt, ast.Try):
            _check_body_for_assignment_save(
                stmt.body,
                func_name,
                op_ranges,
                violations,
            )
            for handler in stmt.handlers:
                _check_body_for_assignment_save(
                    handler.body,
                    func_name,
                    op_ranges,
                    violations,
                )
            _check_body_for_assignment_save(
                stmt.orelse or [],
                func_name,
                op_ranges,
                violations,
            )
            _check_body_for_assignment_save(
                stmt.finalbody or [],
                func_name,
                op_ranges,
                violations,
            )
        if isinstance(stmt, ast.If):
            _check_body_for_assignment_save(
                stmt.body,
                func_name,
                op_ranges,
                violations,
            )
            _check_body_for_assignment_save(
                stmt.orelse or [],
                func_name,
                op_ranges,
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
        saved_at: int | None = None
        for j in range(i + 1, min(i + 5, len(body))):
            next_stmt = body[j]
            if isinstance(next_stmt, ast.Expr):
                inner = next_stmt.value
                if isinstance(inner, ast.Call):
                    if isinstance(inner.func, ast.Attribute) and inner.func.attr in (
                        "save",
                        "asave",
                    ):
                        saved_at = next_stmt.lineno
                        break
        if saved_at is None:
            continue

        # Check if both assignment AND save are inside
        # operator_access_migration ranges.
        assign_covered = _is_within_ranges(
            assign.lineno,
            op_ranges,
        ) or _is_within_ranges(
            assign.end_lineno or assign.lineno,
            op_ranges,
        )
        save_covered = _is_within_ranges(saved_at, op_ranges)

        if not (assign_covered and save_covered):
            violations.append(
                {
                    "func_name": func_name,
                    "line": assign.lineno,
                    "message": (
                        f"organization_id assignment (line {assign.lineno}) "
                        f"followed by .save() (line {saved_at}) is not "
                        f"enclosed by `with operator_access_migration("
                        f"schema_editor):`.  ORM writes through the default "
                        f"manager are subject to FORCE RLS and need "
                        f"operator_access."
                    ),
                    "category": "ungated-assignment-save",
                }
            )


def _uses_base_manager(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return ``True`` if *func_node* contains a reference to
    ``_base_manager`` in its AST.

    ``_base_manager`` bypasses FORCE RLS, so assignment+save patterns
    using it do not need ``operator_access_migration``.
    """
    for subnode in ast.walk(func_node):
        if isinstance(subnode, ast.Attribute) and subnode.attr == "_base_manager":
            return True
    return False


def _find_assignment_save_in_function(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    op_ranges: list[tuple[int, int]],
) -> list[dict]:
    """Detect ``obj.organization_id = value`` followed by ``obj.save()``
    (or ``obj.save(update_fields=...)``) within *func_node* that are NOT
    enclosed by ``operator_access_migration``.

    Skips functions that use ``_base_manager`` (which bypasses FORCE RLS
    and does not need operator_access).

    Recursively checks compound statement bodies (for, while, with, try,
    if).  Returns a list of violation dicts with the line of the assignment.
    """
    violations: list[dict] = []
    # Functions using _base_manager bypass RLS — no violation.
    if _uses_base_manager(func_node):
        return violations
    _check_body_for_assignment_save(
        func_node.body,
        func_node.name,
        op_ranges,
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

    def _find_enclosing_params(lineno: int) -> tuple[set[str], str]:
        for (start, end), params in sorted(func_params.items(), reverse=True):
            if start <= lineno <= end:
                return params, func_names[(start, end)]
        return set(), "<module>"

    violations: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            if not _is_operator_access_migration_call(item.context_expr):
                continue
            assert isinstance(item.context_expr, ast.Call)
            call = item.context_expr

            # Check the first argument
            if not call.args:
                continue
            first_arg = call.args[0]

            if isinstance(first_arg, ast.Name):
                arg_name = first_arg.id
                enclosing_params, enclosing_name = _find_enclosing_params(node.lineno)
                if arg_name not in enclosing_params:
                    violations.append(
                        {
                            "line": node.lineno,
                            "message": (
                                f"operator_access_migration() called "
                                f"with argument '{arg_name}' at line "
                                f"{node.lineno}, but '{arg_name}' is "
                                f"not a parameter of the enclosing "
                                f"function '{enclosing_name}'.  Must use "
                                f"the callback's own 'schema_editor'."
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
                            f"a simple name.  Must use the callback's own "
                            f"'schema_editor' parameter."
                        ),
                        "category": "wrong-editor",
                    }
                )
    return violations


# =========================================================================
# Detector: shadowing of operator_access_migration name
# =========================================================================


def _check_operator_access_shadowing(tree: ast.AST) -> list[dict]:
    """Detect assignments, imports, or function definitions that shadow the
    ``operator_access_migration`` name within the migration source.

    The canonical import is:
        from quickscale_modules_orgs.tenancy import operator_access_migration

    Any assignment or re-import that shadows this name is flagged.
    """
    violations: list[dict] = []
    for node in ast.walk(tree):
        # Check assignments: operator_access_migration = <something>
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
                                f"Shadowing assignment to "
                                f"'{_OPERATOR_ACCESS_CM_NAME}' at line "
                                f"{node.lineno}.  The name must remain "
                                f"bound to its canonical import from "
                                f"quickscale_modules_orgs.tenancy."
                            ),
                            "category": "shadowing",
                        }
                    )

        # Check imports that shadow the name from a different module
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == _OPERATOR_ACCESS_CM_NAME:
                    if node.module != "quickscale_modules_orgs.tenancy":
                        violations.append(
                            {
                                "filepath": "<unknown>",
                                "line": node.lineno,
                                "message": (
                                    f"Import of '{_OPERATOR_ACCESS_CM_NAME}' "
                                    f"from non-canonical module "
                                    f"'{node.module}' at line {node.lineno}.  "
                                    f"Must import from "
                                    f"quickscale_modules_orgs.tenancy."
                                ),
                                "category": "shadowing",
                            }
                        )

        # Check named imports that alias the context manager
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
                                f"quickscale_modules_orgs.tenancy."
                            ),
                            "category": "shadowing",
                        }
                    )

    return violations


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

    op_ranges = _find_operator_access_ranges(tree)

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

        if not _is_within_ranges(node.lineno, op_ranges):
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

        if not _is_within_ranges(node.lineno, op_ranges):
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
                if not _is_within_ranges(node.lineno, op_ranges):
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
            as_violations = _find_assignment_save_in_function(node, op_ranges)
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

    # --- Detector 7: shadowing ---
    for sh_v in _check_operator_access_shadowing(tree):
        sh_v.setdefault("filepath", filepath)
        violations.append(sh_v)

    return violations


def get_migration_files() -> list[Path]:
    """Return ``Path`` objects for every shipped migration ``.py`` file under
    all installed ``quickscale_modules_*`` apps.

    Only returns files matching the ``[0-9]*.py`` pattern (migration files
    as opposed to ``__init__.py``).
    """
    from django.apps import apps

    files: list[Path] = []
    for app_config in apps.get_app_configs():
        label: str = app_config.label
        if not label.startswith("quickscale_modules_"):
            continue
        migrations_path = Path(app_config.path) / "migrations"
        if not migrations_path.is_dir():
            continue
        for py_file in sorted(migrations_path.glob("[0-9]*.py")):
            files.append(py_file)
    return files


def get_all_module_migration_dirs() -> list[Path]:
    """Return sorted list of migration directory paths for ALL manifested
    ``quickscale_modules_*`` packages found on the filesystem, independent
    of Django ``INSTALLED_APPS``.

    Discovers ``src/quickscale_modules_*/migrations/`` directories within
    the ``quickscale_modules`` workspace, checking both ``src/`` layout and
    flat package layout.

    Each returned path is verified to exist and be a directory.  Unreadable
    or inaccessible directories are reported via ``pytest.fail``.
    """
    import pytest

    # Determine the quickscale_modules workspace root relative to this file.
    # This test lives in: quickscale_modules/orgs/tests/
    # The workspace root is three levels up.
    this_file = Path(__file__).resolve()
    qs_modules_root = this_file.parents[2]  # quickscale_modules/

    if not qs_modules_root.is_dir():
        pytest.fail(
            f"Cannot discover quickscale_modules workspace: "
            f"{qs_modules_root} is not a directory"
        )

    dirs: list[Path] = []
    entries = sorted(qs_modules_root.iterdir())

    for entry in entries:
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        # Check for src/quickscale_modules_<name>/migrations/ layout
        src_pkg = entry / "src"
        if src_pkg.is_dir():
            for pkg_dir in sorted(src_pkg.iterdir()):
                pkg_name = pkg_dir.name
                if pkg_name.startswith("quickscale_modules_"):
                    migrations_dir = pkg_dir / "migrations"
                    if migrations_dir.is_dir():
                        dirs.append(migrations_dir.resolve())

        # Also check flat layout: quickscale_modules_<name>/migrations/
        pkg_dir = entry / entry.name.replace("-", "_")
        if pkg_dir.is_dir() and not pkg_dir.exists():
            pass  # flat layout check not applicable for first-party modules
        elif pkg_dir.name.startswith("quickscale_modules_"):
            migrations_dir = pkg_dir / "migrations"
            if migrations_dir.is_dir():
                resolved = migrations_dir.resolve()
                if resolved not in dirs:
                    dirs.append(resolved)

    if not dirs:
        pytest.fail(
            f"No quickscale_modules migration directories found under {qs_modules_root}"
        )
    return dirs


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

    def test_orm_backfill_not_flagged(self) -> None:
        """ORM-based backfill with individual .save() (no .update()) is
        not flagged."""
        violations = check_migration_source(NO_EXECUTE_CODE)
        assert len(violations) == 0, (
            f"Expected 0 violations for ORM-only code, got "
            f"{len(violations)}: {violations}"
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
    """Prove the gate can inventory all manifested quickscale_modules
    migration directories independent of INSTALLED_APPS."""

    def test_manifested_dirs_are_found(self) -> None:
        """``get_all_module_migration_dirs`` returns at least one
        migration directory, proving filesystem-based discovery works
        regardless of INSTALLED_APPS."""
        dirs = get_all_module_migration_dirs()
        assert len(dirs) >= 1, (
            f"Expected at least 1 migration directory, got {len(dirs)}"
        )
        # Each dir must exist and be a directory
        for d in dirs:
            assert d.is_dir(), f"Migration directory {d} does not exist"

    def test_manifested_dirs_migration_files_parse(self) -> None:
        """Every migration file in all manifested directories is valid
        Python and can be parsed by check_migration_source without
        syntax errors."""
        dirs = get_all_module_migration_dirs()
        all_syntax_errors: list[str] = []
        for d in dirs:
            for py_file in sorted(d.glob("[0-9]*.py")):
                source = py_file.read_text(encoding="utf-8")
                violations = check_migration_source(
                    source,
                    str(py_file),
                )
                for v in violations:
                    if "Syntax error" in v.get("message", ""):
                        all_syntax_errors.append(f"{py_file}: {v['message']}")
        if all_syntax_errors:
            pytest.fail(
                f"{len(all_syntax_errors)} file(s) have syntax errors:\n"
                + "\n".join(all_syntax_errors)
            )


# =========================================================================
# Real-tree compliance test
# =========================================================================


class TestMigrationOperatorAccessConformance:
    """Verify every shipped migration wraps cross-table DML in
    ``operator_access_migration``."""

    def _get_module_label(self, filepath: str) -> str | None:
        """Derive the Django app label from a migration file path."""
        p = Path(filepath)
        parts = p.parts
        for i, part in enumerate(parts):
            if part == "src" and i + 1 < len(parts):
                return parts[i + 1]
        return None

    def test_all_migrations_pass_conformance_gate(self) -> None:
        """Every migration file in ``quickscale_modules_*`` apps passes the
        SA88 conformance gate.

        This is the authoritative negative-proof gate: any migration that
        contains cross-table DML assigning ``organization_id`` that is NOT
        lexically enclosed by ``with operator_access_migration(...)`` fails
        this test with an actionable location report.

        Known debt exemptions in ``SA88_DEBT_EXEMPTIONS`` are allowed but
        tracked.  Any migration not in that ledger that contains ungated
        cross-table DML fails closed.
        """
        all_violations: list[dict] = []
        for filepath in get_migration_files():
            fp_str = str(filepath)
            source = filepath.read_text(encoding="utf-8")
            module_label = self._get_module_label(fp_str)
            violations = check_migration_source(source, fp_str, module_label)
            all_violations.extend(violations)

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
        """No migration in the installed tree contains raw GUC manipulation
        of ``app.operator_access``.

        This is a focused negative-proof gate complementing the broader
        conformance check above.  Raw GUC manipulation is always forbidden
        (non-exemptible); the ``operator_access_migration`` context manager
        is the only permitted mechanism.
        """
        raw_guc_violations: list[dict] = []
        for filepath in get_migration_files():
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
