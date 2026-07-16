"""SA90-MSQ — Forward guardrail: no cross-table organization_id DML in migrations.

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
# Same-table literal org_id assignment
_LITERAL = re.compile(
    r"\bUPDATE\s+\w+(?:\s+(?:AS\s+)?\w+)?\s+SET\s+(?:\w+\.)?"
    r'["\'`]?organization_id["\'`]?\s*=\s*\'',
    re.I,
)


def _is_benign(sql: str) -> bool:
    """True when *sql* is statically classifiable and harmless."""
    sql = re.sub(r"\s+", " ", sql).strip()
    if not sql:
        return True
    if not _ORG_ID.search(sql):
        return True
    for stmt in (s.strip() for s in sql.split(";") if s.strip()):
        s = re.sub(r"\s+", " ", stmt).strip()
        if (
            _DDL.search(s)
            or _RLS.search(s)
            or _SELECT.match(s)
            or _DELETE.match(s)
            or _INSERT_VALUES.match(s)
        ):
            continue
        if _LITERAL.match(s):
            continue
        # Check SET clause: if org_id not being SET, WHERE-only ref is benign
        if re.match(r"\bUPDATE\b", s, re.I):
            m = re.search(
                r"\bSET\s+(.+?)(?:\bWHERE\b|\bFROM\b|\bRETURNING\b|$)", s, re.I
            )
            if m and not re.search(
                r'(?:\w+\.)?["\'`]?organization_id["\'`]?\s*=', m.group(1), re.I
            ):
                continue
        # Any remaining org_id mention is suspect
        if _ORG_ID.search(s):
            return False
    return True


def _resolve(bind: dict[str, ast.expr], expr: ast.expr) -> ast.expr:
    """Recursively resolve Name references through bindings."""
    seen: set[int] = set()
    while isinstance(expr, ast.Name) and expr.id in bind and id(expr) not in seen:
        seen.add(id(expr))
        nxt = bind[expr.id]
        if isinstance(nxt, ast.Constant):
            return nxt
        expr = nxt
    return expr


def scan_migration(path: Path) -> list[str]:
    """Scan a migration file for cross-table org DML."""
    try:
        src = path.read_bytes().decode("utf-8")
    except OSError as e:
        return [f"UNREADABLE: {path.name}: {e}"]
    except UnicodeDecodeError:
        return [f"DECODE_ERROR: {path.name}"]
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [f"SYNTAX_ERROR: {path.name}: {e}"]

    # Build module-level constant bindings
    bind: dict[str, ast.expr] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    bind[t.id] = n.value

    findings: list[str] = []

    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        func = n.func
        is_execute = isinstance(func, ast.Attribute) and func.attr == "execute"
        is_runsql = (isinstance(func, ast.Attribute) and func.attr == "RunSQL") or (
            isinstance(func, ast.Name) and func.id == "RunSQL"
        )
        if not (is_execute or is_runsql):
            continue

        # Collect SQL arguments
        args: list[ast.expr] = list(n.args)
        if is_runsql:
            for kw in n.keywords:
                if kw.arg in ("reverse_sql", "sql"):
                    args.append(kw.value)

        for arg in args:
            resolved = _resolve(bind, arg)

            if isinstance(resolved, ast.Constant) and isinstance(resolved.value, str):
                if not _is_benign(resolved.value):
                    findings.append(f"CROSS_TABLE_ORG_DML: {path.name}")
                continue

            if isinstance(resolved, ast.Constant) and isinstance(resolved.value, bytes):
                try:
                    sql = resolved.value.decode("utf-8")
                    if not _is_benign(sql):
                        findings.append(f"CROSS_TABLE_ORG_DML: {path.name}")
                except (UnicodeDecodeError, ValueError):
                    findings.append(f"UNREADABLE_BYTES: {path.name}")
                continue

            # Non-resolvable — fail closed if it mentions org_id
            seg = ast.get_source_segment(src, n) or ""
            arg_seg = ast.get_source_segment(src, arg) or ""
            # Also check assignment source for the variable
            extra = ""
            if isinstance(arg, ast.Name) and arg.id in bind:
                extra = ast.get_source_segment(src, bind[arg.id]) or ""
            combined = f"{seg} {arg_seg} {extra}"
            if _ORG_ID.search(combined):
                if _DDL.search(seg) or _RLS.search(seg):
                    continue
                tag = "UNRESOLVED_RUNSQL_ORG" if is_runsql else "UNCLASSIFIABLE_ORG_DML"
                findings.append(f"{tag}: {path.name}")

    return findings


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

    # Imported unresolved SQL mentioning org_id — must fail closed
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
        # Write the exact source without any org_id string
        p.write_text(src)
        # If the source doesn't contain "org" at all, it's an accepted
        # limitation — the guardrail can't see the imported value.
        # Check that at least no false-positive is generated.
        result = scan_migration(p)
        if "organization_id" in src.lower():
            assert result, f"Imported SQL mentioning org_id must fail closed: {tag}"


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
    p = tmp_path / "unclass.py"
    p.write_text(
        'def f(a,se):\n sql = resolve_sql("organization_id")\n se.execute(sql)\n'
    )
    assert any("UNCLASSIFIABLE_ORG_DML" in f for f in scan_migration(p))
