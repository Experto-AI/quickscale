"""Keep the v88 context coverage aligned with the roadmap's open tickets.

The roadmap is the sole home for schedulable metadata.  The context page may explain
concepts, but it must not restate bands, positions, dependencies, or readiness.  The roadmap
holds open work only and carries no checked entry.  Completed tickets are archived in the
changelog.  The shared SA167 umbrella may still explain the archived SA167a handoff as settled
tree state.  The integration-ready SA167d closeout, green SA167c Phase F, and closed
SA170 statuses are checked as current consumer contracts below; those checks are not mutation
canaries.

Scope, deliberately narrow (2026-08-31).  The three primary live invariants are current-count
agreement, roadmap/context ticket coverage, and the ban on schedulable metadata in conceptual
context.  Retained expected-red canaries prove those parser/guard boundaries, while explicit
current-status contracts preserve the integration-ready SA167d closeout, the green SA167c
Phase-F verdict authorized under ``EV-7``, and the final SA170 closeout.  The suite previously carried twelve
mutation canaries across 496 lines, including one
that mutated a hardcoded ``deps:`` literal naming a specific ticket; archiving that ticket silently
disarmed it, as did roadmap prose that happened to spell the same literal first.  The remaining
canaries are derived from current structure or exercise still-live invariant boundaries rather than
pinning a closed ticket.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest

ROOT = Path(__file__).parents[2]
ROADMAP = ROOT / "docs/technical/roadmap.md"
CONTEXT = ROOT / "docs/technical/v88_ticket_context.md"
DOCS_INDEX = ROOT / "docs/index.md"
TICKET_RE = re.compile(r"\bSA\d+[a-z]?\b")
TICKET_ENTRY_RE = re.compile(
    r"^\s*-\s+\[[^\]]*\]\s+\*\*(SA\d+[a-z]?)\b[^\n]*$", re.MULTILINE
)
OPEN_ENTRY_RE = re.compile(r"^\s*- \[ \] \*\*(SA\d+[a-z]?)\b[^\n]*$", re.MULTILINE)
CLOSED_ENTRY_RE = re.compile(r"^\s*- \[x\] \*\*(SA\d+[a-z]?)\b[^\n]*$", re.MULTILINE)
OPEN_TICKET_RE = re.compile(
    r"^\s*- \[ \] \*\*(SA\d+[a-z]?)\b.*?`((?:Band|Post-v88)[^`]*)`",
    re.MULTILINE,
)
MERGE_ORDER_ENTRY_RE = re.compile(
    r"^\|\s*\d+\s*\|\s*\*\*(SA\d+[a-z]?)\*\*\s*\|[^|\n]*\|[^|\n]*\|\s*(W[123])\s*\|",
    re.MULTILINE,
)
SECTION_RE = re.compile(r"^## (SA\d+[a-z]?[^\n]*)$", re.MULTILINE)
E0_ACCEPTED_TIP = "bd2c291ba2d40494970464741ac51bfd45445a19"
SA167C_RETAINED_PRODUCT = "91fd3bb6e6b638735361b511c1515cddccce5d15"
CURRENT_V88_TIP = "21a33fbf22b033cab07ba63b592e21b999667fb2"
UMBRELLA_TITLE = "SA167a / SA167c — module wiring standardization"
UMBRELLA_MEMBERS = frozenset({"SA167a", "SA167c"})
AUXILIARY_SECTIONS = frozenset({"SA160 / SA161 sequencing note"})
RETAINED_CLOSED_TICKETS: frozenset[str] = frozenset()
ARCHIVED_CONTEXT_TICKETS = frozenset({"SA167a", "SA167b", "SA167c"})
SHARED_POSITION_GROUPS: frozenset[frozenset[str]] = frozenset()


@dataclass(frozen=True)
class TicketMetadata:
    dependencies: frozenset[str]
    kind: str
    merge_position: int | None
    worktree: str | None


def _dependencies(metadata: str) -> frozenset[str]:
    match = re.search(r"\bdeps:\s*(.*?)(?:\s*[·—]|$)", metadata)
    if not match:
        return frozenset()
    dependency_text = match.group(1).strip()
    if re.match(r"none\b", dependency_text, re.IGNORECASE):
        return frozenset()
    dependencies = frozenset(TICKET_RE.findall(dependency_text))
    if not dependencies:
        raise AssertionError(f"unparseable dependency metadata: {dependency_text!r}")
    return dependencies


def _merge_position(metadata: str, kind: str, ticket: str) -> int | None:
    match = re.search(r"\bmerge #(\d+)\b", metadata)
    if kind == "v88" and not match:
        raise AssertionError(f"v88 ticket lacks merge position: {ticket}")
    if kind == "post-v88" and match:
        raise AssertionError(
            f"post-v88 ticket unexpectedly has merge position: {ticket}"
        )
    return int(match.group(1)) if match else None


def _worktree(metadata: str, kind: str, ticket: str) -> str | None:
    match = re.search(r"\bW([123])\b", metadata)
    if kind == "v88" and not match:
        raise AssertionError(f"v88 ticket lacks worktree assignment: {ticket}")
    if kind == "post-v88" and match:
        raise AssertionError(f"post-v88 ticket unexpectedly has worktree: {ticket}")
    return f"W{match.group(1)}" if match else None


def _roadmap_tickets(text: str) -> dict[str, TicketMetadata]:
    entries = list(TICKET_ENTRY_RE.finditer(text))
    unsupported = sorted(
        match.group(1)
        for match in entries
        if not (
            OPEN_ENTRY_RE.fullmatch(match.group(0))
            or CLOSED_ENTRY_RE.fullmatch(match.group(0))
        )
    )
    if unsupported:
        raise AssertionError(f"unsupported roadmap ticket entry shape: {unsupported}")

    closed = set(CLOSED_ENTRY_RE.findall(text))
    if closed != set(RETAINED_CLOSED_TICKETS):
        raise AssertionError(
            "checked roadmap tickets are not permitted; the roadmap holds open work only: "
            f"expected={sorted(RETAINED_CLOSED_TICKETS)}, actual={sorted(closed)}"
        )
    open_entries = OPEN_ENTRY_RE.findall(text)
    duplicates = sorted(
        ticket for ticket, count in Counter(open_entries).items() if count > 1
    )
    if duplicates:
        raise AssertionError(f"duplicate open roadmap ticket: {duplicates}")

    parsed = {match.group(1) for match in OPEN_TICKET_RE.finditer(text)}
    unparseable = sorted(set(open_entries) - parsed)
    if unparseable:
        raise AssertionError(
            f"open roadmap tickets have unparseable classification metadata: {unparseable}"
        )

    tickets: dict[str, TicketMetadata] = {}
    for match in OPEN_TICKET_RE.finditer(text):
        ticket, metadata = match.groups()
        if not re.search(r"\bdeps:\s*", metadata):
            raise AssertionError(f"missing roadmap dependency metadata: {ticket}")
        kind = "post-v88" if "Post-v88" in metadata else "v88"
        tickets[ticket] = TicketMetadata(
            dependencies=_dependencies(metadata),
            kind=kind,
            merge_position=_merge_position(metadata, kind, ticket),
            worktree=_worktree(metadata, kind, ticket),
        )

    unknown = {
        ticket: sorted(item.dependencies - set(tickets) - closed)
        for ticket, item in tickets.items()
        if item.dependencies - set(tickets) - closed
    }
    if unknown:
        raise AssertionError(
            f"roadmap dependencies do not name open tickets: {unknown}"
        )
    return tickets


def _section_blocks(text: str) -> list[tuple[str, str]]:
    matches = list(SECTION_RE.finditer(text))
    return [
        (
            match.group(1),
            text[
                match.start() : matches[index + 1].start()
                if index + 1 < len(matches)
                else len(text)
            ],
        )
        for index, match in enumerate(matches)
    ]


def _context_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for title, section in _section_blocks(text):
        if title in AUXILIARY_SECTIONS:
            continue
        if title == UMBRELLA_TITLE:
            named = set(UMBRELLA_MEMBERS)
        else:
            heading = re.match(r"^(SA\d+[a-z]?)\b", title)
            if not heading:
                raise AssertionError(f"unclassified current-context section: {title}")
            named = {heading.group(1)}
        for ticket in named:
            if ticket in sections:
                raise AssertionError(
                    f"duplicate current-context ticket section: {ticket}"
                )
            sections[ticket] = section
    return sections


def _shared_position_groups(tickets: dict[str, TicketMetadata]) -> set[frozenset[str]]:
    by_position: defaultdict[int, set[str]] = defaultdict(set)
    for ticket, metadata in tickets.items():
        if metadata.merge_position is not None:
            by_position[metadata.merge_position].add(ticket)
    return {frozenset(group) for group in by_position.values() if len(group) > 1}


def _positive_closure_claim(section: str, dependency: str) -> re.Match[str] | None:
    direct = re.search(
        rf"\b{re.escape(dependency)}\b\s+(?:(?:is|was|remains)\s+)?(?:closed|satisfied|settled|complete)\b",
        section,
        re.IGNORECASE,
    )
    if direct:
        return direct
    return re.search(
        rf"\b{re.escape(dependency)}'s\b[^.\n]{{0,80}}\b(?:is|was|are|were|remains|has been)\s+(?:now\s+)?(?:closed|satisfied|settled|complete)\b",
        section,
        re.IGNORECASE,
    )


def _assert_consistent(roadmap_text: str, context_text: str) -> None:
    roadmap = _roadmap_tickets(roadmap_text)
    sections = _context_sections(context_text)
    closed = set(CLOSED_ENTRY_RE.findall(roadmap_text))
    context_tickets = set(sections) - closed - ARCHIVED_CONTEXT_TICKETS
    if context_tickets != set(roadmap):
        raise AssertionError(
            "roadmap/current-context ticket coverage drift: "
            f"missing={sorted(set(roadmap) - context_tickets)}, "
            f"unexpected={sorted(context_tickets - set(roadmap))}"
        )

    actual_shared_groups = _shared_position_groups(roadmap)
    if actual_shared_groups != set(SHARED_POSITION_GROUPS):
        raise AssertionError(
            "shared-position roadmap classification drift: "
            f"expected={sorted(map(sorted, SHARED_POSITION_GROUPS))}, "
            f"actual={sorted(map(sorted, actual_shared_groups))}"
        )

    umbrella = sections["SA167c"]
    status_sections = sections | {ticket: umbrella for ticket in UMBRELLA_MEMBERS}
    for ticket, metadata in roadmap.items():
        for dependency in metadata.dependencies:
            if dependency in closed:
                continue
            claim = _positive_closure_claim(status_sections[ticket], dependency)
            if claim:
                raise AssertionError(
                    f"{ticket} claims roadmap-open dependency {dependency} is closed: {claim.group(0)!r}"
                )


SCHEDULABLE_METADATA_RE = re.compile(r"`(?:Band|Post-v88)[^`\n]*\bdeps:[^`\n]*`")
SEMANTIC_SCHEDULING_RE = re.compile(
    r"(?ix)"
    r"\bSA\d+[a-z]?\b[^.\n]{0,100}"
    r"\b(?:before|after|ahead\s+of|depends?\s+on|blocked?\s+by|"
    r"prerequisite\s+for|scheduled|scheduling|follows?|precedes?|until|"
    r"first\b[^.\n]{0,40}\bthen)\b"
    r"[^.\n]{0,100}\bSA\d+[a-z]?\b"
    r"|\bSA\d+[a-z]?\b\s*(?:→|->)\s*\bSA\d+[a-z]?\b"
)
RETIRED_DJANGO_APPS_DEPENDENCY_RE = re.compile(
    r"\b_migdir\(\)[^.\n]{0,160}\b(?:reads?|uses?|depends?\s+on)\b"
    r"[^.\n]{0,100}`?django_apps:?`?",
    re.IGNORECASE,
)
BROAD_NO_RED_GATE_RE = re.compile(r"\bno gates? (?:is|are) red\b", re.IGNORECASE)
STALE_SA167C_E_OPEN_RE = re.compile(
    r"(?ix)"
    r"\bopen\s+product\s+work\s+is\s+SA167c\s+E/F\b"
    r"|\bSA167c\b[^.\n]{0,80}\b(?:E/F|E\s+(?:and|then)\s+F)\b"
    r"[^.\n]{0,80}\b(?:open|pending|outstanding)\b"
)
STALE_SA167C_CURRENT_RE = re.compile(
    r"\bSA167c\s+(?:remains|is still)\s+open\b"
    r"|\bSA167c\s+is\s+not\s+(?:complete|release-ready)\b"
    r"|\bSA166\s+remains\s+dependent\b"
    r"|\bSA166\b[^.\n]{0,80}\bdeps:\s*SA167c\b"
    r"|\b(?:merge\s+)?position\s+#?21\b[^.\n]{0,80}\b(?:open|head|runnable)\b",
    re.IGNORECASE,
)


def _load_documents() -> tuple[str, str]:
    return ROADMAP.read_text(encoding="utf-8"), CONTEXT.read_text(encoding="utf-8")


_NUMBER_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
    17: "seventeen",
    18: "eighteen",
    19: "nineteen",
    20: "twenty",
}


def _number_word(value: int) -> str:
    if value not in _NUMBER_WORDS:
        raise AssertionError(f"no spelled form for count {value}; extend _NUMBER_WORDS")
    return _NUMBER_WORDS[value]


def _roadmap_block(text: str, start: str, end: str) -> str:
    _, start_separator, remainder = text.partition(start)
    if not start_separator:
        raise AssertionError(f"roadmap block start is missing: {start}")
    block, end_separator, _ = remainder.partition(end)
    if not end_separator:
        raise AssertionError(f"roadmap block end is missing: {end}")
    return block


def _assert_sa167c_current_roadmap_blocks(roadmap_text: str) -> None:
    """Reject contradictions inside the current Band-A and open-work blocks."""
    priority_model = _roadmap_block(
        roadmap_text, "### Priority model", "### Dependency graph and critical path"
    )
    dependency_graph = _roadmap_block(
        roadmap_text,
        "### Dependency graph and critical path",
        "### Track rebalance",
    )
    next_actions = _roadmap_block(
        roadmap_text, "### Next action per lane", "### Track readiness"
    )
    applicable_current_blocks = "\n".join(
        (priority_model, dependency_graph, next_actions)
    )
    broad_no_red = BROAD_NO_RED_GATE_RE.search(applicable_current_blocks)
    assert not broad_no_red, broad_no_red.group(0) if broad_no_red else None
    stale_e_open = STALE_SA167C_E_OPEN_RE.search(applicable_current_blocks)
    assert not stale_e_open, stale_e_open.group(0) if stale_e_open else None

    assert "no provisioning gate is red" in priority_model.lower()
    assert "SA167c verdict is green and archived" in dependency_graph, (
        "SA167c dependency graph must record the archived green verdict"
    )
    assert "start SA166 (#24)" in next_actions


def _assert_lane_assignment_parity(roadmap_text: str) -> None:
    """Derive lane counts from ticket metadata and bind every merge-table row."""
    roadmap = _roadmap_tickets(roadmap_text)
    expected_assignments = {
        ticket: metadata.worktree
        for ticket, metadata in roadmap.items()
        if metadata.kind == "v88"
    }
    merge_entries = MERGE_ORDER_ENTRY_RE.findall(roadmap_text)
    duplicate_merge_entries = sorted(
        ticket
        for ticket, count in Counter(ticket for ticket, _ in merge_entries).items()
        if count > 1
    )
    if duplicate_merge_entries:
        raise AssertionError(
            f"duplicate merge-order ticket rows: {duplicate_merge_entries}"
        )
    merge_assignments = dict(merge_entries)
    if merge_assignments != expected_assignments:
        raise AssertionError(
            "roadmap lane assignment drift between ticket metadata and merge table: "
            f"expected={expected_assignments}, actual={merge_assignments}"
        )

    derived_counts = Counter(expected_assignments.values())
    census = re.search(
        r"Lanes are \*\*W1 (\d+) · W2 (\d+) · W3 (\d+)\*\*", roadmap_text
    )
    assert census is not None
    stated_counts = {
        "W1": int(census.group(1)),
        "W2": int(census.group(2)),
        "W3": int(census.group(3)),
    }
    expected_counts = {lane: derived_counts[lane] for lane in ("W1", "W2", "W3")}
    if stated_counts != expected_counts:
        raise AssertionError(
            "roadmap lane count drift from ticket metadata: "
            f"expected={expected_counts}, actual={stated_counts}"
        )

    dependency_graph = _roadmap_block(
        roadmap_text,
        "### Dependency graph and critical path",
        "### Track rebalance",
    )
    w3_count_word = _number_word(expected_counts["W3"])
    if not re.search(
        rf"\bits {w3_count_word} positions are a \*queue\*",
        dependency_graph,
        re.IGNORECASE,
    ):
        raise AssertionError(
            "W3 dependency-graph prose does not use its derived lane count: "
            f"expected={w3_count_word}"
        )


def _assert_lane_state_snapshot(roadmap_text: str) -> None:
    """Bind the closeout snapshot without conflating refs with dirty worktrees."""
    lane_state = _roadmap_block(
        roadmap_text, "### Lane state", "### PostgreSQL routing"
    )
    rows = {
        worktree: (divergence, tip, standing)
        for worktree, divergence, tip, standing in re.findall(
            r"^\| `(wt-track[123])` \| (\d+ / \d+) \| `([0-9a-f]{8})` \| (.*?) \|$",
            lane_state,
            re.MULTILINE,
        )
    }
    assert set(rows) == {"wt-track1", "wt-track2", "wt-track3"}
    for worktree, (divergence, tip, standing) in rows.items():
        assert divergence == "0 / 0", worktree
        assert tip == CURRENT_V88_TIP[:8], worktree
        assert "branch synchronized" in standing, worktree
        assert "worktree dirty" in standing, worktree
        assert not re.search(r"\bclean\b", standing, re.IGNORECASE), worktree

    assert (
        "distinguishes branch-ref synchronization from working-tree state" in lane_state
    )
    assert re.search(
        r"rather\s+than treating this closeout snapshot as live state", lane_state
    )
    assert "At capture time, no lane branch was ahead" in lane_state


def _assert_status_consumers_agree(roadmap_text: str, docs_index_text: str) -> None:
    """Live counts are *derived* from the roadmap, never pinned to a literal.

    Only the roadmap owns the open-ticket universe.  This check proves the docs hub
    restates whatever the roadmap currently says, so both move together and neither
    needs editing to match a fixture.

    Deliberately absent: any assertion over `docs/others/arch-audit.md` or
    `docs/others/tech-audit.md`.  Those documents are live findings, not a ledger
    (see decisions.md -> Document Responsibilities).  Pinning their counts, finding
    IDs, or prose here forces every regenerated audit to reproduce the previous
    pass's conclusions, which is the opposite of an audit.  Do not add them back.

    Equally absent: literal ticket counts, merge positions, ticket IDs, dates, and
    roadmap prose.  Every one of those goes stale on the next planning pass and is
    paid for by an unrelated edit to this file.
    """
    roadmap = _roadmap_tickets(roadmap_text)
    v88 = {
        ticket: metadata
        for ticket, metadata in roadmap.items()
        if metadata.kind == "v88"
    }
    positions = {
        metadata.merge_position
        for metadata in v88.values()
        if metadata.merge_position is not None
    }
    entry_word = _number_word(len(v88))
    position_word = _number_word(len(positions))

    expected_phrases = {
        "docs/index.md": (
            docs_index_text,
            rf"{entry_word} open v88 ticket entries across {position_word} open merge positions",
        ),
        "docs/technical/roadmap.md": (
            roadmap_text,
            rf"{position_word} open merge positions carrying {entry_word} open ticket entries",
        ),
    }
    for name, (text, pattern) in expected_phrases.items():
        if not re.search(pattern, text, re.IGNORECASE):
            raise AssertionError(
                f"{name} does not restate the roadmap's derived counts "
                f"({len(v88)} entries / {len(positions)} positions): expected {pattern!r}"
            )


def _assert_sa167c_current_status(
    roadmap_text: str,
    context_text: str,
    docs_index_text: str,
    arch_audit_text: str,
    changelog_text: str,
    decisions_text: str,
    implementation_contract_text: str,
    module_extension_text: str,
) -> None:
    """Keep accepted A-E distinct from the completed F verdict."""
    roadmap = _roadmap_tickets(roadmap_text)
    assert "SA167c" not in roadmap
    assert 21 not in {metadata.merge_position for metadata in roadmap.values()}
    assert roadmap["SA166"].dependencies == frozenset()
    assert roadmap["SA164"].dependencies == frozenset({"SA166"})

    latest_closeout = re.search(
        r"(?ms)^- \*\*SA167c Phase F release verdict green\b.*?(?=^- \*\*)",
        changelog_text,
    )
    assert latest_closeout is not None
    current_status_consumers = {
        "CHANGELOG.md": latest_closeout.group(0),
        "docs/index.md": docs_index_text,
        "docs/others/arch-audit.md": arch_audit_text,
        "docs/technical/implementation_contract.md": implementation_contract_text,
        "docs/technical/module-extension.md": module_extension_text,
        "docs/technical/roadmap.md": roadmap_text,
        "docs/technical/v88_ticket_context.md": context_text,
    }
    for path, text in current_status_consumers.items():
        normalized_text = " ".join(text.split())
        assert "SA167c" in normalized_text, path
        assert re.search(r"EV-7", normalized_text), path
        assert re.search(
            r"(?:green|passed|complete|archived)", normalized_text, re.I
        ), path
        assert not re.search(
            r"(?:not yet run|remains outstanding|F remains outstanding|unaccepted|fresh reviewed authority (?:is|are|and a new F verdict are) (?:still )?required)",
            normalized_text,
            re.I,
        ), path
        stale_current = STALE_SA167C_CURRENT_RE.search(normalized_text)
        assert not stale_current, (
            path,
            stale_current.group(0) if stale_current else None,
        )

    assert (
        "Phase F release status and downstream sequencing live in the roadmap"
        in decisions_text
    )
    for text in (
        context_text,
        arch_audit_text,
        implementation_contract_text,
        module_extension_text,
    ):
        normalized_text = " ".join(text.split())
        assert SA167C_RETAINED_PRODUCT in normalized_text
        assert re.search(
            r"phases A-E (?:(?:are|were|remain) )?accepted", normalized_text, re.I
        )

    latest_sa167c_entry = re.search(
        r"(?ms)^- \*\*SA167c Phase F release verdict green\b.*?(?=^- \*\*)",
        changelog_text,
    )
    assert latest_sa167c_entry is not None
    normalized_entry = " ".join(latest_sa167c_entry.group(0).split())
    assert "exit file" in normalized_entry and "containing `0`" in normalized_entry
    assert "all twelve CI stages passed" in normalized_entry
    assert "Core reported **38 passed" in normalized_entry
    assert "CLI **54 passed" in normalized_entry


def _assert_sa170_final_closeout(
    roadmap_text: str,
    context_text: str,
    changelog_text: str,
    status_consumers: dict[str, str],
) -> None:
    """Keep SA170 closed in live ledgers while preserving final evidence."""
    roadmap = _roadmap_tickets(roadmap_text)
    assert "SA170" not in roadmap
    assert all(item.merge_position != 27 for item in roadmap.values())
    assert "## SA170" not in context_text
    assert "#27 are **retired and not" in roadmap_text
    assert roadmap["SA171"].dependencies == frozenset()

    latest_closeout = re.search(r"(?ms)^- \*\*SA170\b.*?(?=^- \*\*)", changelog_text)
    assert latest_closeout is not None
    normalized_closeout = " ".join(latest_closeout.group(0).split())
    assert "QS_E2E_PARALLEL=0" in normalized_closeout
    assert "make test-e2e" in normalized_closeout
    assert "make ci-e2e" in normalized_closeout
    assert "exited **0**" in normalized_closeout
    assert "Core reported **38 passed" in normalized_closeout
    assert "CLI reported **54 passed" in normalized_closeout
    assert "both exact lane cleanups complete" in normalized_closeout
    assert "PostgreSQL `pg18-af10`" in normalized_closeout

    stale_status = re.compile(
        r"SA170 (?:remains|remain|is) open|phase C-release remains unaccepted",
        re.IGNORECASE,
    )
    for name, text in status_consumers.items():
        normalized_text = " ".join(text.split())
        assert not stale_status.search(normalized_text), name


def _assert_sa167d_status(
    roadmap_text: str,
    context_text: str,
    arch_audit_text: str,
    changelog_text: str,
    decisions_text: str,
    implementation_contract_text: str,
    module_extension_text: str,
    state: Literal["integration-ready"],
) -> None:
    """Enforce the reviewed integration-ready state."""
    roadmap = _roadmap_tickets(roadmap_text)
    v88 = {
        ticket: metadata
        for ticket, metadata in roadmap.items()
        if metadata.kind == "v88"
    }
    positions = {
        metadata.merge_position
        for metadata in v88.values()
        if metadata.merge_position is not None
    }

    status_consumers = {
        "CHANGELOG.md": changelog_text,
        "docs/others/arch-audit.md": arch_audit_text,
        "docs/technical/decisions.md": decisions_text,
        "docs/technical/implementation_contract.md": implementation_contract_text,
        "docs/technical/module-extension.md": module_extension_text,
        "docs/technical/roadmap.md": roadmap_text,
        "docs/technical/v88_ticket_context.md": context_text,
    }

    if state != "integration-ready":
        raise AssertionError(f"unknown SA167d status state: {state}")

    assert "SA167d" not in v88
    assert 18 not in positions
    assert len(v88) == 9
    assert len(positions) == 9
    assert v88["SA165"].dependencies == frozenset()
    assert E0_ACCEPTED_TIP in changelog_text
    latest_sa167d_entry = re.search(
        r"(?ms)^- \*\*SA167d\b.*?(?=^- \*\*)", changelog_text
    )
    assert latest_sa167d_entry is not None
    normalized_latest_entry = " ".join(latest_sa167d_entry.group(0).split())
    assert "terminated with exit 143" in normalized_latest_entry
    assert "supplied no gate verdict" in normalized_latest_entry
    assert "exact command rerun returned exit 0" in normalized_latest_entry
    assert "Every lane is clean and behind" not in roadmap_text
    assert "SA167d" in changelog_text and re.search(
        r"archiv(?:e|ed|es)", changelog_text, re.I
    )
    for path, text in status_consumers.items():
        assert "conditional post-integration" in text.lower(), path
        assert "exact-tip" in text.lower(), path


def test_v88_live_status_consumers_derive_current_counts() -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")
    docs_index = DOCS_INDEX.read_text(encoding="utf-8")
    _assert_status_consumers_agree(roadmap, docs_index)
    _assert_sa167c_current_roadmap_blocks(roadmap)
    _assert_lane_assignment_parity(roadmap)
    _assert_lane_state_snapshot(roadmap)
    _assert_sa167d_status(
        roadmap,
        CONTEXT.read_text(encoding="utf-8"),
        (ROOT / "docs/others/arch-audit.md").read_text(encoding="utf-8"),
        (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
        (ROOT / "docs/technical/decisions.md").read_text(encoding="utf-8"),
        (ROOT / "docs/technical/implementation_contract.md").read_text(
            encoding="utf-8"
        ),
        (ROOT / "docs/technical/module-extension.md").read_text(encoding="utf-8"),
        "integration-ready",
    )
    _assert_sa167c_current_status(
        roadmap,
        CONTEXT.read_text(encoding="utf-8"),
        docs_index,
        (ROOT / "docs/others/arch-audit.md").read_text(encoding="utf-8"),
        (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
        (ROOT / "docs/technical/decisions.md").read_text(encoding="utf-8"),
        (ROOT / "docs/technical/implementation_contract.md").read_text(
            encoding="utf-8"
        ),
        (ROOT / "docs/technical/module-extension.md").read_text(encoding="utf-8"),
    )
    _assert_sa170_final_closeout(
        roadmap,
        CONTEXT.read_text(encoding="utf-8"),
        (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
        {
            "docs/index.md": docs_index,
            "docs/others/arch-audit.md": (ROOT / "docs/others/arch-audit.md").read_text(
                encoding="utf-8"
            ),
            "docs/planning/frontend-e2e-coverage.md": (
                ROOT / "docs/planning/frontend-e2e-coverage.md"
            ).read_text(encoding="utf-8"),
            "docs/technical/implementation_contract.md": (
                ROOT / "docs/technical/implementation_contract.md"
            ).read_text(encoding="utf-8"),
            "docs/technical/module-extension.md": (
                ROOT / "docs/technical/module-extension.md"
            ).read_text(encoding="utf-8"),
            "docs/technical/roadmap.md": roadmap,
            "docs/technical/v88_ticket_context.md": CONTEXT.read_text(encoding="utf-8"),
        },
    )


@pytest.mark.parametrize(
    ("current_claim", "contradiction", "error_match"),
    [
        (
            "no provisioning gate is red",
            "no gate is red",
            "no gate is red",
        ),
        (
            "SA167c verdict is green and archived",
            "SA167c verdict is pending",
            "SA167c dependency graph",
        ),
    ],
)
def test_v88_sa167c_current_roadmap_blocks_reject_contradictions(
    current_claim: str,
    contradiction: str,
    error_match: str,
) -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")
    mutated = roadmap.replace(current_claim, contradiction, 1)
    assert mutated != roadmap
    with pytest.raises(AssertionError, match=error_match):
        _assert_sa167c_current_roadmap_blocks(mutated)


@pytest.mark.parametrize(
    ("current_claim", "drifted_claim", "error_match"),
    [
        ("W3 2**", "W3 3**", "lane count drift"),
        (
            "its two positions are a *queue*",
            "its three positions are a *queue*",
            "W3 dependency-graph prose",
        ),
        (
            "| 29 | **SA172** | C | 3 | W3 |",
            "| 29 | **SA172** | C | 3 | W2 |",
            "lane assignment drift",
        ),
    ],
)
def test_v88_lane_assignment_drift_is_expected_red_canary(
    current_claim: str,
    drifted_claim: str,
    error_match: str,
) -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")
    mutated = roadmap.replace(current_claim, drifted_claim, 1)
    assert mutated != roadmap
    with pytest.raises(AssertionError, match=error_match):
        _assert_lane_assignment_parity(mutated)


@pytest.mark.parametrize(
    ("current_claim", "drifted_claim"),
    [
        (
            "| `wt-track1` | 0 / 0 | `21a33fbf` |",
            "| `wt-track1` | 1 / 0 | `a14ea029` |",
        ),
        ("branch synchronized; worktree dirty", "clean"),
    ],
)
def test_v88_lane_state_snapshot_rejects_stale_rows(
    current_claim: str, drifted_claim: str
) -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")
    mutated = roadmap.replace(current_claim, drifted_claim, 1)
    assert mutated != roadmap
    with pytest.raises(AssertionError):
        _assert_lane_state_snapshot(mutated)


def test_v88_sa167c_current_status_rejects_open_dependency_claim() -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")
    context = CONTEXT.read_text(encoding="utf-8")
    docs_index = DOCS_INDEX.read_text(encoding="utf-8")
    arch_audit = (ROOT / "docs/others/arch-audit.md").read_text(encoding="utf-8")
    current_claim = "SA167c is closed and archived; SA166 is now `deps: none`."
    assert current_claim in arch_audit
    mutated_arch_audit = arch_audit.replace(
        current_claim,
        "SA167c remains open and archived; SA166 remains dependent.",
        1,
    )

    with pytest.raises(AssertionError):
        _assert_sa167c_current_status(
            roadmap,
            context,
            docs_index,
            mutated_arch_audit,
            (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
            (ROOT / "docs/technical/decisions.md").read_text(encoding="utf-8"),
            (ROOT / "docs/technical/implementation_contract.md").read_text(
                encoding="utf-8"
            ),
            (ROOT / "docs/technical/module-extension.md").read_text(encoding="utf-8"),
        )


def test_v88_integration_ready_state_rejects_accepted_open_candidate() -> None:
    """Keep the integration-ready branch strict against the accepted-open state."""
    roadmap = ROADMAP.read_text(encoding="utf-8")
    accepted_open_roadmap = (
        roadmap
        + "\n- [ ] **SA167d — accepted-open canary.** `Band B · Tier 2 · W1 · merge #18 · deps: none`\n"
    )
    with pytest.raises(AssertionError, match="SA167d"):
        _assert_sa167d_status(
            accepted_open_roadmap,
            CONTEXT.read_text(encoding="utf-8"),
            (ROOT / "docs/others/arch-audit.md").read_text(encoding="utf-8"),
            (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
            (ROOT / "docs/technical/decisions.md").read_text(encoding="utf-8"),
            (ROOT / "docs/technical/implementation_contract.md").read_text(
                encoding="utf-8"
            ),
            (ROOT / "docs/technical/module-extension.md").read_text(encoding="utf-8"),
            "integration-ready",
        )


def test_v88_status_consumer_count_drift_is_expected_red_canary() -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")
    mutated_index = "The queue holds forty open v88 ticket entries across two open merge positions.\n"
    with pytest.raises(AssertionError, match="does not restate the roadmap"):
        _assert_status_consumers_agree(roadmap, mutated_index)


def test_v88_current_context_covers_roadmap_open_tickets() -> None:
    roadmap, context = _load_documents()
    _assert_consistent(roadmap, context)


def test_v88_context_restates_no_schedulable_roadmap_metadata() -> None:
    _, context = _load_documents()
    assert not SCHEDULABLE_METADATA_RE.findall(context)
    assert not SEMANTIC_SCHEDULING_RE.findall(context)


def test_v88_sa164_context_rejects_retired_django_apps_dependency_claim() -> None:
    _, context = _load_documents()
    sa164_context = _context_sections(context)["SA164"]
    assert not RETIRED_DJANGO_APPS_DEPENDENCY_RE.search(sa164_context)


@pytest.mark.parametrize(
    "claim",
    [
        "SA167a must be merged before SA118.",
        "SA118 follows SA167a.",
        "SA118 cannot start until SA167a closes.",
        "SA167a is a prerequisite for SA118.",
        "SA167a → SA118.",
        "Merge SA167a first, then SA118.",
    ],
)
def test_v88_semantic_scheduling_restatement_is_expected_red_canary(
    claim: str,
) -> None:
    _, context = _load_documents()
    assert SEMANTIC_SCHEDULING_RE.findall(context + f"\n{claim}\n")


@pytest.mark.parametrize(
    "explanation",
    [
        "SA118, SA161, and SA160 touch the same fixture.",
        "SA167a and SA167c share one conceptual umbrella.",
    ],
)
def test_v88_semantic_scheduling_guard_avoids_explanatory_false_positives(
    explanation: str,
) -> None:
    assert not SEMANTIC_SCHEDULING_RE.findall(explanation)


def test_v88_schedulable_metadata_restatement_is_expected_red_canary() -> None:
    _, context = _load_documents()
    assert SCHEDULABLE_METADATA_RE.findall(
        context + "\n`Band B · Tier 1 · W2 · merge #11 · deps: SA167a`\n"
    )


def test_v88_missing_roadmap_open_ticket_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated = (
        roadmap
        + "\n- [ ] **SA999 — expected-red coverage canary.** `Post-v88 · Tier 3 · deps: none`\n"
    )
    with pytest.raises(AssertionError, match="ticket coverage drift"):
        _assert_consistent(mutated, context)


def test_v88_unexpected_current_context_ticket_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated = context + "\n## SA999 — unexpected expected-red canary\n\nbody\n"
    with pytest.raises(AssertionError, match="ticket coverage drift"):
        _assert_consistent(roadmap, mutated)


def test_v88_unexpected_checked_roadmap_entry_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated = (
        roadmap
        + "\n- [x] **SA997 — closed-ticket exclusion canary.** `Post-v88 · Tier 3 · deps: none`\n"
    )
    with pytest.raises(AssertionError, match="checked roadmap tickets"):
        _assert_consistent(mutated, context)


def test_v88_unsupported_roadmap_entry_shape_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated = (
        roadmap
        + "\n- [-] **SA996 — unsupported expected-red canary.** `Post-v88 · Tier 3 · deps: none`\n"
    )
    with pytest.raises(AssertionError, match="unsupported roadmap ticket entry shape"):
        _assert_consistent(mutated, context)


def test_v88_missing_roadmap_dependency_metadata_is_expected_red_canary() -> None:
    """Strip the ``deps:`` clause off whichever ticket the roadmap lists first."""
    roadmap, context = _load_documents()
    entry = OPEN_TICKET_RE.search(roadmap)
    assert entry is not None
    ticket, metadata = entry.groups()
    mutated = roadmap.replace(
        metadata, re.sub(r"\s*·?\s*deps:[^·`]*", "", metadata, count=1), 1
    )
    assert mutated != roadmap
    with pytest.raises(
        AssertionError, match=rf"missing roadmap dependency metadata: {ticket}"
    ):
        _assert_consistent(mutated, context)


def test_v88_unknown_roadmap_dependency_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    entry = next(
        match
        for match in OPEN_TICKET_RE.finditer(roadmap)
        if "deps: none" in match.group(2)
    )
    mutated_entry = entry.group(0).replace("deps: none", "deps: SA999", 1)
    mutated = roadmap.replace(entry.group(0), mutated_entry, 1)
    assert mutated != roadmap
    with pytest.raises(AssertionError, match="dependencies do not name open tickets"):
        _assert_consistent(mutated, context)


def test_v88_dependency_status_contradiction_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    tickets = _roadmap_tickets(roadmap)
    dependent_ticket = next(
        ticket
        for ticket, metadata in tickets.items()
        if metadata.dependencies - RETAINED_CLOSED_TICKETS
    )
    dependency = next(
        iter(tickets[dependent_ticket].dependencies - RETAINED_CLOSED_TICKETS)
    )
    section = _context_sections(context)[dependent_ticket]
    mutated = context.replace(section, section + f"\n{dependency} is closed.\n", 1)
    with pytest.raises(
        AssertionError,
        match=rf"claims roadmap-open dependency {re.escape(dependency)}",
    ):
        _assert_consistent(roadmap, mutated)


def test_v88_current_reconciliation_is_not_labelled_ungraded() -> None:
    current_status_paths = (
        DOCS_INDEX,
        ROOT / "docs/others/arch-audit.md",
        ROADMAP,
        CONTEXT,
        ROOT / "docs/technical/decisions.md",
        ROOT / "docs/technical/implementation_contract.md",
        ROOT / "docs/technical/module-extension.md",
    )

    for path in current_status_paths:
        text = path.read_text(encoding="utf-8")
        assert not re.search(
            r"\bnot(?:\s+been)?\s+independently\s+graded\b", text, re.IGNORECASE
        ), path

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    latest_sa167d_entry = re.search(r"(?ms)^- \*\*SA167d\b.*?(?=^- \*\*)", changelog)
    assert latest_sa167d_entry is not None
    assert "not independently graded" in latest_sa167d_entry.group(0)
    latest_sa167c_entry = re.search(
        r"(?ms)^- \*\*SA167c Phase E accepted; Phase F halted\b.*?(?=^- \*\*)",
        changelog,
    )
    assert latest_sa167c_entry is not None
    assert "not independently graded" in latest_sa167c_entry.group(0)


def _assert_latest_closeout_uses_current_queue_counts(
    roadmap_text: str, changelog_text: str
) -> None:
    roadmap = _roadmap_tickets(roadmap_text)
    v88 = {
        ticket: metadata
        for ticket, metadata in roadmap.items()
        if metadata.kind == "v88"
    }
    positions = {
        metadata.merge_position
        for metadata in v88.values()
        if metadata.merge_position is not None
    }
    expected = (
        f"{_number_word(len(v88))} open v88 ticket entries across "
        f"{_number_word(len(positions))} open merge positions"
    )
    latest_closeout_entry = re.search(
        r"(?ms)^- \*\*SA167c Phase F release verdict green\b.*?(?=^- \*\*)",
        changelog_text,
    )
    assert latest_closeout_entry is not None
    normalized_entry = " ".join(latest_closeout_entry.group(0).split())
    assert expected in normalized_entry


def test_v88_latest_closeout_uses_current_queue_counts() -> None:
    _assert_latest_closeout_uses_current_queue_counts(
        ROADMAP.read_text(encoding="utf-8"),
        (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
    )


def test_v88_latest_closeout_count_drift_is_expected_red_canary() -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    v88 = {
        ticket: metadata
        for ticket, metadata in _roadmap_tickets(roadmap).items()
        if metadata.kind == "v88"
    }
    positions = {
        metadata.merge_position
        for metadata in v88.values()
        if metadata.merge_position is not None
    }
    current_pattern = (
        rf"{_number_word(len(v88))}\s+open\s+v88\s+ticket\s+entries\s+across\s+"
        rf"{_number_word(len(positions))}\s+open\s+merge\s+positions"
    )
    mutated, replacement_count = re.subn(
        current_pattern,
        "one open v88 ticket entries across two open merge positions",
        changelog,
        count=1,
    )

    assert replacement_count == 1
    with pytest.raises(AssertionError):
        _assert_latest_closeout_uses_current_queue_counts(roadmap, mutated)


def test_v88_shared_merge_position_drift_is_expected_red_canary() -> None:
    """Point one v88 ticket at another's merge position and expect the drift error.

    Derived from whatever the roadmap currently holds, so no ticket ID, position, or
    shared-group literal is pinned here.
    """
    roadmap, context = _load_documents()
    v88 = [
        (ticket, metadata)
        for ticket, metadata in _roadmap_tickets(roadmap).items()
        if metadata.kind == "v88" and metadata.merge_position is not None
    ]
    assert len(v88) >= 2
    (victim, victim_metadata), (_, donor_metadata) = v88[0], v88[1]
    entry = re.search(
        rf"^\s*- \[ \] \*\*{victim}\b.*?`((?:Band|Post-v88)[^`]*)`",
        roadmap,
        re.MULTILINE,
    )
    assert entry is not None
    mutated_roadmap = roadmap.replace(
        entry.group(1),
        entry.group(1).replace(
            f"merge #{victim_metadata.merge_position}",
            f"merge #{donor_metadata.merge_position}",
            1,
        ),
        1,
    )
    assert mutated_roadmap != roadmap

    with pytest.raises(
        AssertionError, match="shared-position roadmap classification drift"
    ):
        _assert_consistent(mutated_roadmap, context)
