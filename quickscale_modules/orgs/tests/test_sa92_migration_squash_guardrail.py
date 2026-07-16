"""SA92 — Forward guardrail: no cross-table organization_id DML in migrations.

Scans ``schema_editor.execute()`` and ``migrations.RunSQL()`` (including
``reverse_sql``) across all module migrations.  Splits multi-statement
SQL on ``;`` so DDL cannot exempt adjacent DML.  Fails closed on
unresolved/imported/dynamic SQL that mentions ``organization_id``.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
MODS = ROOT / "quickscale_modules"

# -- Classification regexes ---------------------------------------------------
_DDL = re.compile(
    r"\b(ALTER|CREATE|DROP)\s+(TABLE|POLICY|INDEX|TRIGGER|FUNCTION|VIEW|COLUMN|CONSTRAINT|SCHEMA)\b",
    re.I,
)
_RLS = re.compile(
    r"\b(ENABLE|FORCE|DISABLE|NO\s+FORCE)\s+ROW\s+LEVEL\s+SECURITY\b", re.I
)
_SELECT = re.compile(r"^\s*SELECT\b", re.I)
# Quote/schema-qualified org_id
_ORG_ID = re.compile(r'(?:\w+\.)?["\'`]?organization_id["\'`]?', re.I)
_DELETE = re.compile(r"^\s*DELETE\b", re.I)
# INSERT VALUES (not INSERT ... SELECT) is benign
_INSERT_VALUES = re.compile(r"^\s*INSERT\s+INTO\b(?!.*\bSELECT\b)", re.I)
# Same-table literal org_id assignment (also parameterized).
# Rejects cross-table prefixes on organization_id: only bare
# ``organization_id`` (optionally quoted) is accepted as the SET target.
_LITERAL = re.compile(
    r"\bUPDATE\s+\w+(?:\s+(?:AS\s+)?\w+)?\s+SET\s+"
    r'["\'`]?organization_id["\'`]?\s*=\s*'
    r"(?:'[^']*'|%[sd]|%\([^)]+\)s|\$\d+)"
    # Hard boundary: forbid SQL concatenation/arithmetic operators or
    # function calls right after the approved RHS so suffixes like
    # ``|| (SELECT …)`` cannot pass through as a literal assignment.
    r"(?!\s*(?:\|\||\+|\())",
    re.I,
)


def _strip_sql_comments(sql: str) -> str:
    """Remove SQL block comments (/* */) and line comments (--).

    Quote-aware with PostgreSQL 18 dialect support:
    - Single-quoted string literals with doubled-escape quotes ('').
    - Double-quoted identifiers with doubled-escape quotes ("").
    - E-strings (``E'...'``, ``B'...'``, ``X'...'``, ``U&'...'``).
    - Dollar-quoted bodies (``$$...$$``, ``$tag$...$tag$``).
    ``--`` and ``/*`` inside any quoted region are NOT treated as
    comment delimiters.
    """
    out: list[str] = []
    i, n = 0, len(sql)
    in_sq = False  # single-quoted string literal (including E'' etc)
    in_dq = False  # double-quoted identifier
    in_dollar = False  # dollar-quoted body
    dollar_tag: str | None = None

    while i < n:
        ch = sql[i]

        # --- Dollar-quoted string start ---
        if not in_sq and not in_dq and not in_dollar and ch == "$":
            rest = sql[i + 1 :]
            m = re.match(r"([a-zA-Z_]\w*)?\$", rest)
            if m:
                tag = m.group(1) or ""
                in_dollar = True
                dollar_tag = tag
                # Consume the entire opening delimiter: $ (ch) + tag + $
                out.append(ch)
                i += 1
                if m.group(1):
                    out.append(m.group(1))
                out.append("$")
                i += m.end()
                continue

        if in_dollar:
            out.append(ch)
            i += 1
            if ch == "$" and not dollar_tag:
                # $$ — check for closing $$
                if i < n and sql[i] == "$":
                    out.append(sql[i])
                    i += 1
                    in_dollar = False
            elif ch == "$" and dollar_tag:
                # $tag$ — check for closing $tag$
                if sql[i:].startswith(dollar_tag + "$"):
                    end_len = len(dollar_tag) + 1
                    out.append(sql[i : i + end_len])
                    i += end_len
                    in_dollar = False
                    dollar_tag = None
            continue

        # --- Toggle quote state ---
        if ch == "'" and not in_dq and not in_dollar:
            in_sq = not in_sq
            out.append(ch)
            i += 1
            continue
        if ch == '"' and not in_sq and not in_dollar:
            in_dq = not in_dq
            out.append(ch)
            i += 1
            continue

        # --- Inside a single-quoted string ---
        if in_sq:
            out.append(ch)
            i += 1
            # '' is an escaped single-quote, NOT the end of the string
            if ch == "'" and i < n and sql[i] == "'":
                out.append(sql[i])
                i += 1
            continue

        # --- Inside a double-quoted identifier ---
        if in_dq:
            out.append(ch)
            i += 1
            # "" is an escaped double-quote inside an identifier
            if ch == '"' and i < n and sql[i] == '"':
                out.append(sql[i])
                i += 1
            continue

        # --- Not inside any quote / dollar body ---
        # Line comment  --  (not inside a string)
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            end = sql.find("\n", i + 2)
            if end == -1:
                break  # rest of the input is comment
            out.append("\n")
            i = end + 1
            continue
        # Block comment  /* ... */  (not inside a string)
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            end = sql.find("*/", i + 2)
            if end == -1:
                break
            out.append(" ")
            i = end + 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _split_sql(sql: str) -> list[str]:
    """Split SQL on ``;`` outside string literals and dollar-quoted bodies.

    PostgreSQL 18 dialect: handles single/double-quoted strings with
    doubled-escape quotes, E-strings, and dollar-quoted bodies.
    """
    stmts: list[str] = []
    cur: list[str] = []
    in_sq = False
    in_dq = False
    in_dollar = False
    dollar_tag: str | None = None
    i, n = 0, len(sql)

    while i < n:
        ch = sql[i]

        # Dollar-quoted start
        if not in_sq and not in_dq and not in_dollar and ch == "$":
            rest = sql[i + 1 :]
            m = re.match(r"([a-zA-Z_]\w*)?\$", rest)
            if m:
                tag = m.group(1) or ""
                in_dollar = True
                dollar_tag = tag
                # Consume entire opening delimiter
                cur.append(ch)
                i += 1
                if m.group(1):
                    cur.append(m.group(1))
                cur.append("$")
                i += m.end()
                continue

        if in_dollar:
            cur.append(ch)
            i += 1
            if ch == "$" and not dollar_tag:
                if i < n and sql[i] == "$":
                    cur.append(sql[i])
                    i += 1
                    in_dollar = False
            elif ch == "$" and dollar_tag:
                if sql[i:].startswith(dollar_tag + "$"):
                    end_len = len(dollar_tag) + 1
                    cur.append(sql[i : i + end_len])
                    i += end_len
                    in_dollar = False
                    dollar_tag = None
            continue

        # Quote toggling
        if ch == "'" and not in_dq and not in_dollar:
            in_sq = not in_sq
            cur.append(ch)
            i += 1
            # Handle '' escape inside single-quoted string
            if in_sq and i < n and sql[i] == "'":
                cur.append(sql[i])
                i += 1
            continue

        if ch == '"' and not in_sq and not in_dollar:
            in_dq = not in_dq
            cur.append(ch)
            i += 1
            # Handle "" escape inside double-quoted identifier
            if in_dq and i < n and sql[i] == '"':
                cur.append(sql[i])
                i += 1
            continue

        if ch == ";" and not in_sq and not in_dq and not in_dollar:
            stmts.append("".join(cur))
            cur = []
            i += 1
            continue

        cur.append(ch)
        i += 1

    remaining = "".join(cur)
    if remaining:
        stmts.append(remaining)
    return stmts


def _is_benign(sql: str) -> bool:
    """True when *sql* is statically classifiable and harmless."""
    sql = _strip_sql_comments(sql)
    sql = re.sub(r"\s+", " ", sql).strip()
    if not sql:
        return True
    if not _ORG_ID.search(sql):
        return True
    for raw in _split_sql(sql):
        stmt = raw.strip()
        if not stmt:
            continue
        stmt = _strip_sql_comments(stmt)
        stmt = re.sub(r"\s+", " ", stmt).strip()
        if (
            _DDL.search(stmt)
            or _RLS.search(stmt)
            or _SELECT.match(stmt)
            or _DELETE.match(stmt)
            or _INSERT_VALUES.match(stmt)
        ):
            continue
        if _LITERAL.match(stmt):
            continue
        # Check SET clause: if org_id not being SET, WHERE-only ref is benign
        if re.match(r"\bUPDATE\b", stmt, re.I):
            m = re.search(
                r"\bSET\s+(.+?)(?:\bWHERE\b|\bFROM\b|\bRETURNING\b|$)", stmt, re.I
            )
            if m and not re.search(
                r'(?:\w+\.)?["\'`]?organization_id["\'`]?\s*=', m.group(1), re.I
            ):
                continue
        # Any remaining org_id mention is suspect
        if _ORG_ID.search(stmt):
            return False
    return True


# -- Scope-aware AST resolution helpers ---------------------------------------


def _resolve_value(
    expr: ast.expr,
    scope_stack: list[dict[str, ast.expr]],
) -> ast.expr:
    """Resolve *expr* through the scope stack (innermost scope first).

    Follows name chains, resolves string concatenation (BinOp Add)
    recursively, and returns the first concrete value found.
    Returns *expr* unchanged when resolution fails.
    """
    seen: set[int] = set()
    # Resolve concatenation: ``'a' + 'b' + var``
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        left = _resolve_value(expr.left, scope_stack)
        right = _resolve_value(expr.right, scope_stack)
        if (
            isinstance(left, ast.Constant)
            and isinstance(left.value, str)
            and isinstance(right, ast.Constant)
            and isinstance(right.value, str)
        ):
            return ast.Constant(value=left.value + right.value)
        return expr
    while isinstance(expr, ast.Name):
        if id(expr) in seen:
            break
        seen.add(id(expr))
        found: ast.expr | None = None
        for scope in reversed(scope_stack):
            if expr.id in scope:
                found = scope[expr.id]
                break
        if found is None:
            break
        if isinstance(found, ast.Constant):
            return found
        expr = found
    return expr


def _build_import_names(tree: ast.AST) -> set[str]:
    """Return set of names imported from other modules, anywhere in the AST.

    For unaliased dotted imports (``import os.path``) binds the root name
    (``os``) so that attribute-chain references are recognised as imported.
    """
    imports: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for alias in n.names:
                name = alias.asname or alias.name
                imports.add(name)
                # Bind root name for dotted imports (e.g. ``import os.path``)
                if "." in name and not alias.asname:
                    imports.add(name.split(".", 1)[0])
        elif isinstance(n, ast.ImportFrom):
            for alias in n.names:
                imports.add(alias.asname or alias.name)
    return imports


def _is_import_ref(node: ast.expr, imports: set[str]) -> bool:
    """Check if an expression chain references an imported name.

    Handles:
    * Direct names (``SQL``)
    * Attribute chains (``config.SQL``)
    * Call wrappers (``get_sql()`` — the callable itself is imported)
    """
    if isinstance(node, ast.Name):
        return node.id in imports
    if isinstance(node, ast.Attribute):
        return _is_import_ref(node.value, imports)
    if isinstance(node, ast.Call):
        return _is_import_ref(node.func, imports)
    return False


def _walk_scope_calls(node: ast.AST):
    """Yield ``ast.Call`` nodes in *node* without entering nested scope
    boundaries (``FunctionDef``, ``AsyncFunctionDef``, ``ClassDef``)."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return
    if isinstance(node, ast.Call):
        yield node
    for child in ast.iter_child_nodes(node):
        yield from _walk_scope_calls(child)


def _scan_scope(
    stmts: list[ast.stmt],
    scope_stack: list[dict[str, ast.expr]],
    imports: set[str],
    source: str,
    path_name: str,
) -> list[str]:
    """Walk statements in lexical order with scope-aware bindings.

    Maintains a binding scope stack so that variable definitions are
    resolved call-order lexically (the value in effect at the call site)
    and scope boundaries (function/class definitions) create fresh
    inner scopes.

    Control-flow bodies (``If``, ``For``, ``While``, ``Try``, ``With``)
    are walked with the same scope so that assignments inside branches
    are visible at call sites within the same function body.
    """
    findings: list[str] = []
    current_scope: dict[str, ast.expr] = {}
    scope_stack.append(current_scope)

    for node in stmts:
        # --- Update bindings in lexical order ---
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    current_scope[target.id] = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.value is not None:
                current_scope[node.target.id] = node.value
        # --- Import bindings are not added to scope — the existing
        # _is_import_ref / imports-set mechanism handles import detection
        # without collapsing Name nodes to Constants prematurely.
        # Function parameters are handled via param_scope in the
        # FunctionDef recursion below.

        # --- Recurse into scope boundaries (fresh inner scopes) ---
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Add function parameters to a param scope visible inside the body
            param_scope: dict[str, ast.expr] = {}
            for arg in node.args.args + node.args.kwonlyargs:
                param_scope[arg.arg] = ast.Constant(value=None)
            if node.args.vararg:
                param_scope[node.args.vararg.arg] = ast.Constant(value=None)
            if node.args.kwarg:
                param_scope[node.args.kwarg.arg] = ast.Constant(value=None)
            for arg in node.args.posonlyargs:
                param_scope[arg.arg] = ast.Constant(value=None)
            # param_scope sits between outer scopes and the body's local scope
            findings.extend(
                _scan_scope(
                    node.body, scope_stack + [param_scope], imports, source, path_name
                )
            )
            continue
        if isinstance(node, ast.ClassDef):
            findings.extend(
                _scan_scope(node.body, list(scope_stack), imports, source, path_name)
            )
            continue

        # --- Recurse into control-flow bodies (same scope for branch assignments) ---
        _bodies: list[list[ast.stmt]] = []
        if isinstance(node, (ast.If, ast.For, ast.While)):
            _bodies.append(node.body)
            if node.orelse:
                _bodies.append(node.orelse)
        elif isinstance(node, ast.Try):
            _bodies.append(node.body)
            for handler in node.handlers:
                _bodies.append(handler.body)
            if node.orelse:
                _bodies.append(node.orelse)
            if node.finalbody:
                _bodies.append(node.finalbody)
        elif isinstance(node, (ast.With, ast.AsyncWith, ast.AsyncFor)):
            _bodies.append(node.body)
        if _bodies:
            for body in _bodies:
                findings.extend(
                    _scan_scope(body, scope_stack, imports, source, path_name)
                )
            continue

        # --- Process Call nodes at THIS scope level ---
        for call in _walk_scope_calls(node):
            func = call.func
            is_execute = isinstance(func, ast.Attribute) and func.attr == "execute"
            is_runsql = (isinstance(func, ast.Attribute) and func.attr == "RunSQL") or (
                isinstance(func, ast.Name) and func.id == "RunSQL"
            )
            if not (is_execute or is_runsql):
                continue

            # Collect SQL arguments
            sql_args: list[ast.expr] = []
            if is_execute:
                # First positional and/or sql= keyword
                if call.args:
                    sql_args.append(call.args[0])
                for kw in call.keywords:
                    if kw.arg == "sql":
                        sql_args.append(kw.value)
            if is_runsql:
                # Only first 2 positional args are sql and reverse_sql
                sql_args.extend(call.args[:2])
                for kw in call.keywords:
                    if kw.arg in ("reverse_sql", "sql"):
                        sql_args.append(kw.value)

            for arg in sql_args:
                resolved = _resolve_value(arg, scope_stack)

                # Skip None values (e.g. reverse_sql=None)
                if isinstance(resolved, ast.Constant) and resolved.value is None:
                    continue

                if isinstance(resolved, ast.Constant) and isinstance(
                    resolved.value, str
                ):
                    if not _is_benign(resolved.value):
                        findings.append(f"CROSS_TABLE_ORG_DML: {path_name}")
                    continue

                if isinstance(resolved, ast.Constant) and isinstance(
                    resolved.value, bytes
                ):
                    try:
                        sql = resolved.value.decode("utf-8")
                        if not _is_benign(sql):
                            findings.append(f"CROSS_TABLE_ORG_DML: {path_name}")
                    except (UnicodeDecodeError, ValueError):
                        findings.append(f"UNREADABLE_BYTES: {path_name}")
                    continue

                # Imported unresolvable SQL — fail closed (no org_id needed)
                if is_runsql and _is_import_ref(resolved, imports):
                    findings.append(f"UNRESOLVED_IMPORTED_SQL: {path_name}")
                    continue
                if is_execute and _is_import_ref(resolved, imports):
                    findings.append(f"UNRESOLVED_IMPORTED_SQL: {path_name}")
                    continue

                # Non-resolvable — fail closed if it mentions org_id
                seg = ast.get_source_segment(source, call) or ""
                arg_seg = ast.get_source_segment(source, arg) or ""
                extra = ""
                # Resolve scope-stack source for unresolvable name
                if isinstance(arg, ast.Name):
                    for scope in reversed(scope_stack):
                        if arg.id in scope:
                            extra = ast.get_source_segment(source, scope[arg.id]) or ""
                            break
                combined = f"{seg} {arg_seg} {extra}"
                if _ORG_ID.search(combined):
                    if _DDL.search(seg) or _RLS.search(seg):
                        continue
                    tag = (
                        "UNRESOLVED_RUNSQL_ORG"
                        if is_runsql
                        else "UNCLASSIFIABLE_ORG_DML"
                    )
                    findings.append(f"{tag}: {path_name}")

    scope_stack.pop()
    return findings


def scan_migration(path: Path) -> list[str]:
    """Scan a migration file for cross-table org DML.

    Uses a scope-aware, source-ordered walker that resolves variable
    bindings call-order lexically.
    """
    try:
        source = path.read_bytes().decode("utf-8")
    except OSError as e:
        return [f"UNREADABLE: {path.name}: {e}"]
    except UnicodeDecodeError:
        return [f"DECODE_ERROR: {path.name}"]
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"SYNTAX_ERROR: {path.name}: {e}"]

    imports = _build_import_names(tree)
    return _scan_scope(tree.body, [], imports, source, path.name)


# -- Helpers ------------------------------------------------------------------


def _manifest() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for d in sorted(MODS.iterdir()):
        p = d / "module.yml"
        if p.is_file():
            data = yaml.safe_load(p.read_text()) or {}
            if isinstance(data, dict) and "name" in data:
                result[str(data["name"])] = data
    return result


def _migdir(name: str, data: dict[str, Any]) -> Path | None:
    for label in data.get("django_apps") or []:
        if label.startswith("quickscale_modules_"):
            d = MODS / name / "src" / label / "migrations"
            if d.is_dir():
                return d
    d = MODS / name / "src" / f"quickscale_modules_{name}" / "migrations"
    return d if d.is_dir() else None


# -- Tests --------------------------------------------------------------------


def test_discovery() -> None:
    m = _manifest()
    for name in (
        "orgs",
        "auth",
        "blog",
        "crm",
        "forms",
        "listings",
        "billing",
        "social",
        "notifications",
        "backups",
    ):
        assert name in m and _migdir(name, m[name]) is not None
    assert len(m) >= 12


def test_real_tree() -> None:
    findings: list[str] = []
    scanned = 0
    for name, data in _manifest().items():
        if name in ("analytics", "storage", "teams"):
            continue
        d = _migdir(name, data)
        if d is None:
            continue
        for pf in sorted(d.iterdir()):
            if pf.suffix != ".py" or pf.name == "__init__.py" or not pf.is_file():
                continue
            scanned += 1
            findings.extend(f"{name}/{pf.name}: {f}" for f in scan_migration(pf))
    assert scanned > 0
    assert not findings, "Cross-table org DML detected:\n" + "\n".join(findings)


def test_canaries(tmp_path: Path) -> None:
    """Cross-table org DML patterns that MUST be caught."""
    bodies = [
        "UPDATE c SET organization_id = (SELECT organization_id FROM p WHERE p.id = c.p_id)",
        "UPDATE t SET organization_id = s.organization_id FROM src s WHERE t.s_id = s.id",
        "INSERT INTO c (id, organization_id) SELECT nextval('s'), s.organization_id FROM src s",
        "update c set organization_id = (select organization_id from p where p.id = c.p_id)",
        'UPDATE c SET "organization_id" = (SELECT organization_id FROM p WHERE p.id = c.p_id)',
        "UPDATE t SET schema.table.organization_id = (SELECT id FROM p)",
    ]
    for i, body in enumerate(bodies):
        # execute canary
        p = tmp_path / f"e{i}.py"
        p.write_text(f"SQL={body!r}\ndef f(a,se):\n se.execute(SQL)\n")
        assert scan_migration(p), f"Execute canary {i}: {body[:50]}"
        # RunSQL canary
        p = tmp_path / f"r{i}.py"
        p.write_text(
            f"from django.db import migrations\nSQL={body!r}\nclass M(migrations.Migration):\n operations=[migrations.RunSQL(SQL)]\n"
        )
        assert scan_migration(p), f"RunSQL canary {i}: {body[:50]}"

    # Mixed DDL+DML — DDL cannot exempt DML
    mixed = "ALTER TABLE t ADD COLUMN x int; UPDATE c SET organization_id = (SELECT organization_id FROM p WHERE p.id = c.p_id)"
    p = tmp_path / "mixed.py"
    p.write_text(
        f"from django.db import migrations\nM={mixed!r}\nclass Mx(migrations.Migration):\n operations=[migrations.RunSQL(M)]\n"
    )
    assert scan_migration(p), "Mixed DDL+DML should be caught"

    # Indirect constant chain
    p = tmp_path / "indirect.py"
    p.write_text(
        "T='UPDATE c SET organization_id=(SELECT organization_id FROM p WHERE p.id=c.p_id)'\nX=T\nY=X\ndef f(a,se):\n se.execute(Y)\n"
    )
    assert scan_migration(p), "Indirect constant chain should be caught"

    # Imported unresolved SQL — must fail closed even without org_id in name
    for tag, src in [
        (
            "execute_imported",
            "def f(a,se):\n from somewhere import SQL\n se.execute(SQL)\n",
        ),
        (
            "runsql_imported",
            "from somewhere import SQL\nfrom django.db import migrations\nclass M(migrations.Migration):\n operations=[migrations.RunSQL(SQL)]\n",
        ),
    ]:
        p = tmp_path / f"{tag}.py"
        p.write_text(src)
        result = scan_migration(p)
        assert any("UNRESOLVED_IMPORTED_SQL" in f for f in result), (
            f"Imported SQL must fail closed even without org_id in name: {tag}"
        )

    # Imported SQL via attribute chain
    p = tmp_path / "imported_attr.py"
    p.write_text(
        "from django.conf import settings\n"
        "SQL = settings.SOME_SQL\n"
        "def f(a,se):\n se.execute(SQL)\n"
    )
    result = scan_migration(p)
    assert any("UNRESOLVED_IMPORTED_SQL" in f for f in result), (
        "Imported SQL via attribute chain must fail closed"
    )

    # Parameterized same-table UPDATE — must be benign
    p = tmp_path / "param_benign.py"
    p.write_text(
        'def f(a,se):\n se.execute("UPDATE t SET organization_id = %s WHERE id = 1")\n'
    )
    result = scan_migration(p)
    assert not result, "Parameterized same-table UPDATE should be benign"

    # SQL-comment-obscured cross-table org_id — must be caught
    # The comment is inside the SQL but the cross-table ref is real DML
    p = tmp_path / "comment_obscured.py"
    p.write_text(
        "SQL = 'UPDATE c SET organization_id = "
        "(SELECT organization_id FROM p WHERE p.id = c.p_id)'\n"
        "def f(a,se):\n se.execute(SQL)\n"
    )
    result = scan_migration(p)
    assert result, "Cross-table org_id in SQL must be caught"

    # Benign SQL with org_id only in comments — not flagged
    p = tmp_path / "comment_benign.py"
    body = "UPDATE t SET name = 'x' /* organization_id is not being changed */ WHERE id = 1"
    p.write_text(
        f"from django.db import migrations\nB={body!r}\n"
        f"class M(migrations.Migration):\n operations=[migrations.RunSQL(B)]\n"
    )
    result = scan_migration(p)
    assert not result, "Benign SQL with org_id only in comments should not be flagged"

    # --- CR-SA90-MSQ-002 additions ---

    # execute(sql=...) keyword form — sql= must be scanned
    p = tmp_path / "execute_kw_sql.py"
    p.write_text(
        "SQL='UPDATE c SET organization_id=(SELECT organization_id FROM p WHERE p.id=c.p_id)'\n"
        "def f(a,se):\n se.execute(sql=SQL)\n"
    )
    result = scan_migration(p)
    assert result, "execute(sql=...) keyword form must be caught"

    # Second positional params in execute(sql, params) are NOT scanned as SQL
    p = tmp_path / "second_param_ignored.py"
    p.write_text(
        "def f(a,se):\n"
        " se.execute('UPDATE t SET organization_id = %s WHERE id = 1',\n"
        "            'not-sql')\n"
    )
    result = scan_migration(p)
    assert not result, (
        "Second positional arg to execute is params, not SQL — must be benign"
    )

    # Cross-table prefix on organization_id in LITERAL pattern — must be caught
    # (UPDATE t SET src.organization_id = %s is NOT same-table assignment)
    p = tmp_path / "literal_cross_table_prefix.py"
    p.write_text(
        "def f(a,se):\n"
        " se.execute('UPDATE t SET src.organization_id = %s WHERE id = 1')\n"
    )
    result = scan_migration(p)
    assert any(
        "CROSS_TABLE_ORG_DML" in f or "UNCLASSIFIABLE_ORG_DML" in f for f in result
    ), "Cross-table prefix on org_id in LITERAL must be caught"

    # Imported call wrapper (get_sql()) — must fail closed
    p = tmp_path / "imported_wrapper.py"
    p.write_text(
        "from somewhere import get_sql\ndef f(a,se):\n se.execute(get_sql())\n"
    )
    result = scan_migration(p)
    assert any("UNRESOLVED_IMPORTED_SQL" in f for f in result), (
        "Imported call wrapper must fail closed"
    )

    # --- Branch-local order: assignment inside if body ---
    p = tmp_path / "branch_if.py"
    p.write_text(
        "def f(a,se):\n"
        " if True:\n"
        '  SQL = "UPDATE c SET organization_id = (SELECT organization_id FROM p WHERE p.id = c.p_id)"\n'
        "  se.execute(SQL)\n"
    )
    result = scan_migration(p)
    assert any("CROSS_TABLE_ORG_DML" in f for f in result), (
        "Branch-local assignment inside if body must be caught"
    )

    # --- Concatenation provenance: sql_a + sql_b ---
    p = tmp_path / "concat.py"
    p.write_text(
        "A='UPDATE c SET organization_id = (SELECT organization_id '\n"
        "B='FROM p WHERE p.id = c.p_id)'\n"
        "def f(a,se):\n se.execute(A + B)\n"
    )
    result = scan_migration(p)
    assert any("CROSS_TABLE_ORG_DML" in f for f in result), (
        "Concatenated SQL strings must be resolved and caught"
    )

    # --- Dotted import root ---
    p = tmp_path / "dotted_import_root.py"
    p.write_text(
        "import os.path\n"
        "SQL = os.path.join('UPDATE', 'c', 'SET', 'organization_id = (SELECT organization_id FROM p)')\n"
        "def f(a,se):\n se.execute(SQL)\n"
    )
    result = scan_migration(p)
    assert any("UNRESOLVED_IMPORTED_SQL" in f for f in result), (
        "Dotted import root must be recognised as imported ref"
    )

    # --- RHS hard boundary: || suffix with cross-table ref ---
    p = tmp_path / "rhs_suffix_cross.py"
    p.write_text(
        "def f(a,se):\n"
        " se.execute(\"UPDATE t SET organization_id = 'prefix-' || (SELECT organization_id FROM p WHERE p.id = t.p_id) WHERE id = 1\")\n"
    )
    result = scan_migration(p)
    assert any("CROSS_TABLE_ORG_DML" in f for f in result), (
        "RHS with || suffix concealing cross-table ref must be caught"
    )

    # --- Dollar-quoted body: ; inside $$ must not split the statement ---
    # If the semicolon inside $$ were treated as a separator, the cross-table
    # UPDATE would be split from the ;-containing part and potentially missed.
    p = tmp_path / "dollar_semicolon.py"
    p.write_text(
        "def f(a,se):\n"
        ' se.execute("UPDATE c SET organization_id = (SELECT organization_id FROM p WHERE p.id = c.p_id) $$ contains ; inside $$ ")\n'
    )
    result = scan_migration(p)
    assert any("CROSS_TABLE_ORG_DML" in f for f in result), (
        "Cross-table ref with ; inside $$ must still be caught (no false split)"
    )

    # --- E-string preserved as string content ---
    p = tmp_path / "e_string.py"
    p.write_text(
        "def f(a,se):\n se.execute(\"SELECT E'\\\\x' || organization_id FROM p\")\n"
    )
    # The E-string produces a string constant that contains a harmless
    # organization_id reference in a read-only SELECT context.
    result = scan_migration(p)
    assert not result, "E-string in read-only SELECT must be benign"

    # --- RunSQL third positional arg ignored ---
    p = tmp_path / "runsql_third_arg.py"
    p.write_text(
        "from django.db import migrations\n"
        "class M(migrations.Migration):\n"
        " operations=[migrations.RunSQL(\n"
        "  'UPDATE t SET organization_id = %s WHERE id = 1',\n"
        "  None,\n"
        "  state_operations=[],\n"
        " )]\n"
    )
    result = scan_migration(p)
    assert not result, (
        "Third positional RunSQL arg (state_operations) must not be scanned as SQL"
    )


def test_benign(tmp_path: Path) -> None:
    """Patterns that must NOT trigger a finding."""
    cases = [
        "SELECT * FROM t WHERE organization_id = (SELECT id FROM o WHERE slug='t')",
        "UPDATE t SET organization_id = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890' WHERE id = 1",
        "UPDATE t SET name = 'x' WHERE organization_id = 'uuid'",
        "ALTER TABLE t ENABLE ROW LEVEL SECURITY; CREATE POLICY p ON t FOR ALL USING (organization_id = current_setting('x')::uuid)",
        "ALTER TABLE child ADD CONSTRAINT f FOREIGN KEY (organization_id) REFERENCES p(id)",
        "ALTER TABLE t DROP COLUMN x",
        "DELETE FROM t WHERE organization_id = 'uuid'",
        "INSERT INTO t (name, value) VALUES ('x', 1)",
    ]
    for i, body in enumerate(cases):
        p = tmp_path / f"b{i}.py"
        p.write_text(
            f"from django.db import migrations\nB={body!r}\nclass M(migrations.Migration):\n operations=[migrations.RunSQL(B)]\n"
        )
        assert not scan_migration(p), f"Benign {i} should not be flagged: {body[:60]}"

    # via execute
    p = tmp_path / "b_exec.py"
    p.write_text(
        "def f(a,se):\n se.execute(\"UPDATE t SET organization_id = 'abc' WHERE id = 1\")\n"
    )
    assert not scan_migration(p), "Same-table literal via execute should be benign"

    p = tmp_path / "b_select_exec.py"
    p.write_text(
        "def f(a,se):\n se.execute('SELECT * FROM t WHERE organization_id = (SELECT id FROM o)')\n"
    )
    assert not scan_migration(p), "Read-only SELECT via execute should be benign"


def test_fail_closed(tmp_path: Path) -> None:
    """Unparseable content and unresolvable org_id refs must fail."""
    p = tmp_path / "syntax.py"
    p.write_text("def f(:\n")
    assert any("SYNTAX_ERROR" in f for f in scan_migration(p))

    p = tmp_path / "decode.py"
    p.write_bytes(b"\xff\xfe\x00\x01")
    assert any("DECODE_ERROR" in f for f in scan_migration(p))

    # Unclassifiable execute arg mentioning org_id
    # Use module-level assignment so lexical-order binding captures it
    p = tmp_path / "unclass.py"
    p.write_text(
        'sql = resolve_sql("organization_id")\ndef f(a,se):\n se.execute(sql)\n'
    )
    assert any("UNCLASSIFIABLE_ORG_DML" in f for f in scan_migration(p))
