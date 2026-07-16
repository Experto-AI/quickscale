"""SA92 — Forward guardrail: no cross-table organization_id DML in migrations.

Bounded literal tripwire (maintainer-selected Option 1, 2026-07-16).
This is a deliberately shallow smoke alarm, NOT a soundness proof.
It detects the literal ``UPDATE … SET organization_id`` cross-table shape
and relies on the checked-in pg_policies/catalog/data parity gate as the
authoritative proof that the cross-org-migration class stays empty.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
MODS = ROOT / "quickscale_modules"

# -- Bounded tripwire ------------------------------------------------------------
# Intentionally not a full SQL parser. Catches the most common cross-table
# DML shape: ``UPDATE <table> SET organization_id = <non-literal>``.
# False negatives are accepted because the pg_policies/catalog/data parity
# gate against v87 is the authoritative proof the class stays empty.
_CROSS_TABLE_ORG_DML = re.compile(
    r"\bUPDATE\s+\w+(?:\s+(?:AS\s+)?\w+)?\s+SET\s+"
    r'["\'`]?organization_id["\'`]?\s*=\s*'
    r"(?!\s*(?:'[^']*'|%[sd]|%\([^)]+\)s))",
    re.I,
)

# Allowlist for known benign cross-table patterns. Must be reviewed
# whenever a new migration is added that triggers the tripwire.
_ALLOWLIST: list[re.Pattern] = []


# -- Helpers --------------------------------------------------------------------


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


# -- Tests ----------------------------------------------------------------------


def test_discovery() -> None:
    """Each packaged module has a migration directory."""
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


def test_no_cross_table_org_dml() -> None:
    """Bounded tripwire: no migration contains cross-table organization_id DML."""
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
            text = pf.read_text(encoding="utf-8")
            for match in _CROSS_TABLE_ORG_DML.finditer(text):
                if any(a.search(match.group()) for a in _ALLOWLIST):
                    continue
                line_num = text[: match.start()].count("\n") + 1
                findings.append(f"{name}/{pf.name}:{line_num}: {match.group()!r}")
    assert scanned > 0, "No migration files scanned"
    assert not findings, "Cross-table organization_id DML detected:\n" + "\n".join(
        findings
    )


# -- Canary tests (bounded) -----------------------------------------------------
# These prove the tripwire activates on the dangerous cross-table pattern
# and stays silent on legitimate same-table assignments.


def test_canary_cross_table_update() -> None:
    """Cross-table UPDATE must be caught by the tripwire."""
    sql = (
        "UPDATE c SET organization_id = "
        "(SELECT organization_id FROM p WHERE p.id = c.p_id)"
    )
    assert _CROSS_TABLE_ORG_DML.search(sql), "Cross-table UPDATE must match tripwire"


def test_canary_same_table_literal() -> None:
    """Same-table literal UPDATE must NOT trigger the tripwire."""
    sql = "UPDATE t SET organization_id = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890' WHERE id = 1"
    assert not _CROSS_TABLE_ORG_DML.search(sql), (
        "Same-table literal UPDATE must not match tripwire"
    )


def test_canary_parameterized_update() -> None:
    """Parameterized UPDATE must NOT trigger the tripwire."""
    sql = "UPDATE t SET organization_id = %s WHERE id = 1"
    assert not _CROSS_TABLE_ORG_DML.search(sql), (
        "Parameterized UPDATE must not match tripwire"
    )


def test_canary_select_read() -> None:
    """Read-only SELECT with organization_id must NOT trigger the tripwire."""
    sql = "SELECT * FROM t WHERE organization_id = (SELECT id FROM o)"
    assert not _CROSS_TABLE_ORG_DML.search(sql), (
        "Read-only SELECT must not match tripwire"
    )


def test_canary_cross_table_quoted() -> None:
    """Quoted organization_id in cross-table UPDATE must be caught."""
    sql = (
        'UPDATE c SET "organization_id" = '
        "(SELECT organization_id FROM p WHERE p.id = c.p_id)"
    )
    assert _CROSS_TABLE_ORG_DML.search(sql), (
        "Quoted org_id in cross-table UPDATE must match tripwire"
    )


def test_canary_named_parameter() -> None:
    """Named parameter placeholder must NOT trigger the tripwire."""
    sql = "UPDATE t SET organization_id = %(org_id)s WHERE id = 1"
    assert not _CROSS_TABLE_ORG_DML.search(sql), (
        "Named parameter must not match tripwire"
    )
