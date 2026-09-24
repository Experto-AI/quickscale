"""Check schedule structure, not acceptance evidence or prose."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
TICKET = r"SA\d+[a-z]?"
RETAINED_CLOSED_TICKETS = {
    "SA152",
    "SA160",
    "SA177",
    "SA180",
    "SA181",
    "SA182",
    "SA183",
    "SA184",
    "SA185",
    "SA186",
    "SA187",
    "SA188",
    "SA189",
    "SA190",
    "SA192",
    "SA193",
    "SA194",
    "SA195",
    "SA196",
    "SA197",
    "SA198",
    "SA199",
    "SA200",
    "SA201",
    "SA202",
    "SA203",
    "SA205",
    "SA206",
    "SA207",
    "SA208",
    "SA209",
    "SA210",
    "SA211",
    "SA213",
}
COLUMNS = [
    "Ticket",
    "Delivery",
    "Horizon",
    "Track",
    "Depends on",
    "Release requirement",
]


def _unique(values: list[str], label: str) -> set[str]:
    duplicates = [value for value, count in Counter(values).items() if count > 1]
    assert not duplicates, f"duplicate {label}: {duplicates}"
    return set(values)


def _tables(text: str) -> list[list[list[str]]]:
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in [*text.splitlines(), ""]:
        if line.strip().startswith("|"):
            current.append(
                [cell.strip() for cell in line.strip().strip("|").split("|")]
            )
        elif current:
            tables.append(current)
            current = []
    return tables


def _roadmap_tickets(text: str) -> set[str]:
    entries = re.findall(
        rf"^[ \t]*- \[([^\]]*)\] \*\*({TICKET})\b([^\n]*)$", text, re.MULTILINE
    )
    assert entries, "no ticket entries"
    assert all(state in {" ", "x"} for state, _, _ in entries), (
        "unsupported ticket state"
    )
    assert all(re.fullmatch(r" — .+\*\*", title) for _, _, title in entries), (
        "invalid ticket header"
    )
    _unique([ticket for _, ticket, _ in entries], "roadmap ticket")
    checked = {ticket for state, ticket, _ in entries if state == "x"}
    assert checked <= RETAINED_CLOSED_TICKETS, f"unsupported checked tickets: {checked}"
    tickets = {ticket for state, ticket, _ in entries if state == " "}
    assert tickets, "no open ticket entries"
    tables = [table for table in _tables(text) if table[0] == COLUMNS]
    assert len(tables) == 1, "expected one canonical schedule"
    table = tables[0]
    assert (
        len(table) >= 3
        and len(table[1]) == len(COLUMNS)
        and all(re.fullmatch(r":?-{3,}:?", cell) for cell in table[1])
    ), "invalid schedule separator"
    rows = table[2:]
    assert all(len(row) == len(COLUMNS) for row in rows), "invalid row width"
    scheduled = _unique([row[0] for row in rows], "scheduled ticket")
    assert all(re.fullmatch(TICKET, ticket) for ticket in scheduled), (
        "invalid scheduled ID"
    )
    assert scheduled == tickets, "schedule coverage mismatch"
    horizons: dict[str, str] = {}
    requirements: dict[str, str] = {}
    dependencies: dict[str, set[str]] = {}
    for ticket, delivery, horizon, track, dependency_text, requirement in rows:
        assert delivery and requirement, (
            f"missing delivery or release requirement: {ticket}"
        )
        assert horizon in {"v88", "post-v88"}, f"invalid horizon: {ticket}"
        allowed_requirements = (
            {"Required", "Optional"}
            if horizon == "v88"
            else {"Deferred", "Inventory only"}
        )
        assert requirement in allowed_requirements, (
            f"invalid release requirement: {ticket}"
        )
        assert track in {"1", "2", "3"}, f"invalid track: {ticket}"
        assert dependency_text == "—" or re.fullmatch(
            rf"{TICKET}(?:,\s*{TICKET})*", dependency_text
        ), f"invalid dependencies: {ticket}"
        deps = set(re.findall(TICKET, dependency_text))
        assert deps <= tickets, f"unknown dependency: {ticket}"
        assert ticket not in deps, f"self dependency: {ticket}"
        horizons[ticket] = horizon
        requirements[ticket] = requirement
        dependencies[ticket] = deps
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(ticket: str) -> None:
        assert ticket not in visiting, f"dependency cycle: {ticket}"
        if ticket in visited:
            return
        visiting.add(ticket)
        for dependency in dependencies[ticket]:
            visit(dependency)
        visiting.remove(ticket)
        visited.add(ticket)

    for ticket in tickets:
        visit(ticket)
        assert horizons[ticket] != "v88" or all(
            horizons[dependency] == "v88" for dependency in dependencies[ticket]
        ), f"v88 depends on post-v88: {ticket}"
        assert requirements[ticket] != "Required" or all(
            requirements[dependency] == "Required"
            for dependency in dependencies[ticket]
        ), f"required task has non-required prerequisite: {ticket}"
    return tickets


def test_roadmap_schedule() -> None:
    _roadmap_tickets((ROOT / "docs/technical/roadmap.md").read_text())


def test_docs_index_links_to_roadmap() -> None:
    text = (ROOT / "docs/index.md").read_text()
    assert re.search(r"\[[^\]]+\]\(technical/roadmap\.md\)", text)


@pytest.fixture
def roadmap() -> str:
    """Synthetic tickets keep controls independent of the live backlog."""
    return """# Roadmap
| Ticket | Delivery | Horizon | Track | Depends on | Release requirement |
| --- | --- | --- | --- | --- | --- |
| SA900 | First delivery | v88 | 1 | — | Required |
| SA901 | Second delivery | v88 | 2 | SA900 | Required |
| SA902 | Later delivery | post-v88 | 3 | SA901 | Deferred |

- [ ] **SA900 — First delivery**
- [ ] **SA901 — Second delivery**
- [ ] **SA902 — Later delivery**
"""


def test_synthetic_valid_roadmap(roadmap: str) -> None:
    _roadmap_tickets(roadmap)


@pytest.mark.parametrize(
    ("old", "new", "error"),
    [
        ("[ ] **SA900", "[y] **SA900", "unsupported ticket state"),
        ("- [ ] **SA900", "  - [X] **SA900", "unsupported ticket state"),
        ("[ ] **SA901", "[ ] **SA900", "duplicate roadmap"),
        ("| SA901 |", "| SA900 |", "duplicate scheduled"),
        ("| SA902 |", "| SA903 |", "schedule coverage"),
        ("| 1 |", "| 4 |", "invalid track"),
        ("| v88 | 1", "| next | 1", "invalid horizon"),
        ("| SA900 | Required", "| unknown | Required", "invalid dependencies"),
        ("| SA900 | Required", "| SA999 | Required", "unknown dependency"),
        ("| SA900 | Required", "| SA901 | Required", "self dependency"),
        ("| — | Required", "| SA901 | Required", "dependency cycle"),
        ("| post-v88 | 3", "| v88 | 3 | extra", "row width"),
        (
            "| v88 | 1 | — | Required",
            "| post-v88 | 1 | — | Deferred",
            "v88 depends on post-v88",
        ),
        ("| Required |", "| Maybe |", "invalid release requirement"),
        ("| Required |", "| Deferred |", "invalid release requirement"),
        ("| Deferred |", "| Required |", "invalid release requirement"),
        ("| — | Required", "| — | Optional", "non-required prerequisite"),
        (
            "**SA900 — First delivery**",
            "**SA900 — First delivery** `Track 1`",
            "header",
        ),
    ],
)
def test_rejects_invalid_roadmap(roadmap: str, old: str, new: str, error: str) -> None:
    assert old in roadmap
    with pytest.raises(AssertionError, match=error):
        _roadmap_tickets(roadmap.replace(old, new, 1))


def test_rejects_duplicate_schedule(roadmap: str) -> None:
    table = roadmap[roadmap.index("| Ticket") : roadmap.index("- [ ]")]
    with pytest.raises(AssertionError, match="one canonical schedule"):
        _roadmap_tickets(roadmap + table)


@pytest.mark.parametrize("closed_ticket", sorted(RETAINED_CLOSED_TICKETS))
def test_accepts_checked_ticket_outside_open_schedule(
    roadmap: str, closed_ticket: str
) -> None:
    closed_roadmap = (
        roadmap.replace("SA902", closed_ticket)
        .replace(
            f"| {closed_ticket} | Later delivery | post-v88 | 3 | SA901 | Deferred |\n",
            "",
        )
        .replace(f"- [ ] **{closed_ticket}", f"- [x] **{closed_ticket}")
    )
    _roadmap_tickets(closed_roadmap)
