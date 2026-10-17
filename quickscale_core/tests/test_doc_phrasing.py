"""Authoritative docs state binding rules, not soft recommendations or dated logs."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
OWNERSHIP_MAP = ROOT / "docs/technical/decisions.md"
SOFT_WORDS = re.compile(
    r"\b(should|prefer|preferred|preferably|consider|ideally|typically|usually|"
    r"generally|recommended|where possible|if possible|try to|may want)\b",
    re.IGNORECASE,
)
DATED_LOG = re.compile(r"^(Audited:|>\s*\*\*Re-run pass)", re.MULTILINE)


def _authoritative_docs() -> list[Path]:
    """Read the **A** rows of decisions.md § Document Responsibilities."""
    text = OWNERSHIP_MAP.read_text(encoding="utf-8")
    section = text.split("## Document Responsibilities", 1)[1].split("\n## ", 1)[0]
    docs = []
    for name in re.findall(
        r"^\| ([\w./-]+\.md) \|[^\n]*\| \*\*A\*\* \|$", section, re.MULTILINE
    ):
        candidates = (
            [ROOT / name]
            if "/" in name
            else [ROOT / "docs/technical" / name, ROOT / name]
        )
        path = next((c for c in candidates if c.is_file()), None)
        assert path is not None, f"ownership map names a missing document: {name}"
        docs.append(path)
    return docs


def _prose(text: str) -> str:
    """Drop code blocks, inline code, quoted terms and comments, which may name soft words."""
    text = re.sub(
        r"```.*?```|<!--.*?-->",
        lambda m: "\n" * m.group().count("\n"),
        text,
        flags=re.DOTALL,
    )
    return re.sub(r"`[^`\n]*`|\"[^\"\n]*\"", "", text)


def test_ownership_map_names_authoritative_docs() -> None:
    assert len(_authoritative_docs()) >= 5


@pytest.mark.parametrize("path", _authoritative_docs(), ids=lambda p: p.name)
def test_authoritative_doc_uses_binding_wording(path: Path) -> None:
    lines = _prose(path.read_text(encoding="utf-8")).splitlines()
    soft = [
        f"{n}: {line.strip()}"
        for n, line in enumerate(lines, 1)
        if SOFT_WORDS.search(line)
    ]
    assert not soft, (
        "soft wording in an authoritative doc (use MUST / MUST NOT):\n"
        + "\n".join(soft)
    )


@pytest.mark.parametrize("path", _authoritative_docs(), ids=lambda p: p.name)
def test_authoritative_doc_carries_no_audit_log(path: Path) -> None:
    assert not DATED_LOG.search(path.read_text(encoding="utf-8"))
