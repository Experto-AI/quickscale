"""Keep the v88 context coverage aligned with the roadmap's open tickets.

The roadmap is the sole home for schedulable metadata.  The context page may explain
concepts, but it must not restate bands, positions, dependencies, or readiness.  The roadmap
holds open work only and carries no checked entry.  Completed tickets are archived in the
changelog.  The shared SA167c context may still explain the archived SA167a handoff as
settled tree state.  SA167d remains open until its D/E handoff is accepted.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
ROADMAP = ROOT / "docs/technical/roadmap.md"
CONTEXT = ROOT / "docs/technical/v88_ticket_context.md"
DOCS_INDEX = ROOT / "docs/index.md"
ARCH_AUDIT = ROOT / "docs/others/arch-audit.md"
TECH_AUDIT = ROOT / "docs/others/tech-audit.md"
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
SECTION_RE = re.compile(r"^## (SA\d+[a-z]?[^\n]*)$", re.MULTILINE)

UMBRELLA_TITLE = "SA167c — module wiring standardization"
UMBRELLA_MEMBERS = frozenset({"SA167c", "SA167d"})
AUXILIARY_SECTIONS = frozenset({"SA160 / SA161 sequencing note"})
RETAINED_CLOSED_TICKETS: frozenset[str] = frozenset()
ARCHIVED_CONTEXT_TICKETS = frozenset({"SA167a", "SA167b"})
SHARED_POSITION_GROUPS = {frozenset({"SA135", "SA163"})}


@dataclass(frozen=True)
class TicketMetadata:
    dependencies: frozenset[str]
    kind: str
    merge_position: int | None


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
            named = UMBRELLA_MEMBERS
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
    if actual_shared_groups != SHARED_POSITION_GROUPS:
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


def _load_documents() -> tuple[str, str]:
    return ROADMAP.read_text(encoding="utf-8"), CONTEXT.read_text(encoding="utf-8")


def _number_word(value: int) -> str:
    words = {
        8: "eight",
        9: "nine",
        10: "ten",
        11: "eleven",
        12: "twelve",
        13: "thirteen",
        14: "fourteen",
    }
    return words[value]


def _assert_current_status_consumers(
    roadmap_text: str,
    context_text: str,
    docs_index_text: str,
    arch_audit_text: str,
    tech_audit_text: str,
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
    assert (len(v88), len(positions)) == (10, 9)
    assert "SA151" not in roadmap
    assert "SA142" not in roadmap
    assert "SA167a" not in roadmap
    assert "SA169" not in roadmap
    assert "SA167d" in roadmap
    assert 3 not in positions
    assert 8 not in positions
    assert 10 not in positions
    assert 11 not in positions
    assert 17 not in positions
    assert 18 in positions
    assert 13 not in positions
    assert 26 not in positions
    assert re.search(r"Positions [^\n]*#3[^\n]*", roadmap_text)
    assert re.search(r"Positions [^\n]*#8[^\n]*", roadmap_text)
    assert re.search(r"Positions [^\n]*#10[^\n]*", roadmap_text)
    assert re.search(r"Positions [^\n]*#11[^\n]*", roadmap_text)
    assert re.search(r"Positions [^\n]*#13[^\n]*", roadmap_text)
    assert re.search(r"Positions [^\n]*#17[^\n]*", roadmap_text)
    retired_positions = re.search(
        r"Positions (?P<body>.*?) are \*\*retired and not\s+reused\*\*",
        roadmap_text,
        re.DOTALL,
    )
    assert retired_positions is not None
    assert "#18" not in retired_positions.group("body")
    assert re.search(r"Positions [^\n]*#26[^\n]*", roadmap_text)
    assert not re.search(r"^## SA151\b", context_text, re.MULTILINE)
    assert not re.search(r"^## SA142\b", context_text, re.MULTILINE)
    assert not re.search(r"^## SA169\b", context_text, re.MULTILINE)
    assert "SA167b" not in _context_sections(context_text)
    assert "SA124" not in _context_sections(context_text)
    assert set(CLOSED_ENTRY_RE.findall(roadmap_text)) == set()

    assert "SA124" not in roadmap
    assert "SA123" not in roadmap
    assert v88["SA167d"].dependencies == frozenset()
    assert "SA118" not in v88
    assert v88["SA167c"].dependencies == frozenset()
    assert v88["SA165"].dependencies == frozenset({"SA167d"})
    assert v88["SA164"].dependencies == frozenset({"SA166"})
    assert roadmap["SA152"].dependencies == frozenset()
    assert v88["SA135"].dependencies == frozenset()
    assert v88["SA163"].dependencies == frozenset({"SA135"})
    assert v88["SA170"].dependencies == frozenset({"SA135"})
    assert "use the same twelve databases" in roadmap_text
    assert re.search(
        r"own all twelve databases first.*?ownership must be restored",
        roadmap_text,
        re.DOTALL,
    )
    # Structural facts only.  Do not add assertions that pin the roadmap's narrative
    # prose: they force the planner to carry sentences it would otherwise retire, which
    # is how this document previously grew past 850 lines.
    assert "W2 sets the release date" in roadmap_text

    current_handoff = re.search(
        r"\*\*State \(measured 2026-08-27\): partial delivery merged into `v88`\.\*\*"
        r"(?P<body>.*?)\*\*Remaining plan",
        roadmap_text,
        re.DOTALL,
    )
    assert current_handoff is not None
    handoff_text = current_handoff.group(0)
    assert "Phases P/A/B and C/D are accepted" in handoff_text
    assert "E was\n  dispatched but is not accepted" in handoff_text
    assert "in flight on `wt-track3`" not in roadmap_text
    assert "uncommitted working tree" not in roadmap_text
    assert "ready to continue from strict C acceptance" not in handoff_text
    assert "W2 has released the shared PostgreSQL cluster" not in handoff_text

    # W1: SA167d is a phase-E acceptance, not a merge-back-only ticket.
    assert "phases A-D accepted, phase E outstanding" in roadmap_text
    assert "This is not a merge-back-only ticket" in roadmap_text

    entry_word = _number_word(len(v88))
    position_word = _number_word(len(positions))
    expected_phrases = {
        docs_index_text: rf"{entry_word} open v88 ticket entries across {position_word} open merge positions",
        arch_audit_text: rf"{entry_word} open v88 ticket entries[^\n]*{position_word} open merge positions",
        roadmap_text: rf"{position_word} open merge positions carrying {entry_word} open ticket entries",
    }
    for text, pattern in expected_phrases.items():
        assert re.search(pattern, text, re.IGNORECASE), pattern

    summary = tech_audit_text.split("## Summary table", 1)[1].split("## Findings", 1)[0]
    severities = re.findall(
        r"^\| `[^`]+` \(TA\d+\) \| \*{0,2}(S[1-4])\*{0,2} \|",
        summary,
        re.MULTILINE,
    )
    assert Counter(severities) == Counter({"S3": 1, "S4": 2})
    assert re.search(
        r"S1 \*\*0\*\*.*S2 \*\*0\*\*.*S3 \*\*1\*\*.*S4 \*\*2\*\*.*Total 3 open",
        summary,
        re.DOTALL,
    )


def test_v88_live_status_consumers_derive_current_counts_and_dependencies() -> None:
    _assert_current_status_consumers(
        ROADMAP.read_text(encoding="utf-8"),
        CONTEXT.read_text(encoding="utf-8"),
        DOCS_INDEX.read_text(encoding="utf-8"),
        ARCH_AUDIT.read_text(encoding="utf-8"),
        TECH_AUDIT.read_text(encoding="utf-8"),
    )


def test_v88_current_context_covers_roadmap_open_tickets() -> None:
    roadmap, context = _load_documents()
    _assert_consistent(roadmap, context)


def test_v88_context_restates_no_schedulable_roadmap_metadata() -> None:
    _, context = _load_documents()
    assert not SCHEDULABLE_METADATA_RE.findall(context)
    assert not SEMANTIC_SCHEDULING_RE.findall(context)


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
    roadmap, context = _load_documents()
    mutated = roadmap.replace("merge #15 · deps: SA135", "merge #15", 1)
    with pytest.raises(
        AssertionError, match="missing roadmap dependency metadata: SA163"
    ):
        _assert_consistent(mutated, context)


def test_v88_unknown_roadmap_dependency_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated = roadmap.replace("deps: SA135", "deps: SA999", 1)
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


def test_v88_shared_merge_position_drift_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated_roadmap = roadmap.replace(
        "SA163 — Derive the CI PostgreSQL environment from one authoritative source.** "
        "`Band B · Tier 2 · W3 · merge #15",
        "SA163 — Derive the CI PostgreSQL environment from one authoritative source.** "
        "`Band B · Tier 2 · W3 · merge #26",
        1,
    )
    assert mutated_roadmap != roadmap

    with pytest.raises(
        AssertionError, match="shared-position roadmap classification drift"
    ):
        _assert_consistent(mutated_roadmap, context)
