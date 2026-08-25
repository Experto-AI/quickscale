"""Keep the v88 context coverage aligned with the roadmap's open tickets.

The roadmap is the sole home for schedulable metadata.  The context page may explain
concepts, but it must not restate bands, positions, dependencies, or readiness.  The
shared SA167 umbrella is allowed to mention the completed SA167a handoff; the retained
marker itself remains owned by the roadmap.
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

UMBRELLA_TITLE = "SA167a / SA167b / SA167c / SA167d — module wiring standardization"
UMBRELLA_MEMBERS = frozenset({"SA167a", "SA167b", "SA167c", "SA167d"})
AUXILIARY_SECTIONS = frozenset({"SA160 / SA161 sequencing note"})
RETAINED_CLOSED_TICKETS = frozenset({"SA167a"})
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
            "checked roadmap tickets do not match the retained completion marker: "
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
    context_tickets = set(sections) - closed
    if context_tickets != set(roadmap):
        raise AssertionError(
            "roadmap/current-context ticket coverage drift: "
            f"missing={sorted(set(roadmap) - context_tickets)}, "
            f"unexpected={sorted(context_tickets - set(roadmap))}"
        )

    if _shared_position_groups(roadmap) != SHARED_POSITION_GROUPS:
        raise AssertionError("shared-position roadmap classification drift")

    umbrella = sections["SA167a"]
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


def _load_documents() -> tuple[str, str]:
    return ROADMAP.read_text(encoding="utf-8"), CONTEXT.read_text(encoding="utf-8")


def test_v88_current_context_matches_roadmap_open_tickets() -> None:
    roadmap, context = _load_documents()
    _assert_consistent(roadmap, context)


def test_v88_context_restates_no_schedulable_roadmap_metadata() -> None:
    _, context = _load_documents()
    assert not SCHEDULABLE_METADATA_RE.findall(context)


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


def test_v88_retained_marker_set_is_expected_red_canary() -> None:
    roadmap, _ = _load_documents()
    mutated = roadmap.replace("- [x] **SA167a", "- [ ] **SA167a", 1)
    with pytest.raises(AssertionError, match="checked roadmap tickets"):
        _roadmap_tickets(mutated)


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
    section = _context_sections(context)["SA142"]
    mutated = context.replace(section, section + "\nSA151 is closed.\n", 1)
    with pytest.raises(AssertionError, match="claims roadmap-open dependency SA151"):
        _assert_consistent(roadmap, mutated)


def test_v88_shared_merge_position_drift_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated = roadmap.replace(
        "SA163 — Derive the CI PostgreSQL environment from one authoritative source.** `Band B · Tier 2 · W3 · merge #15",
        "SA163 — Derive the CI PostgreSQL environment from one authoritative source.** `Band B · Tier 2 · W3 · merge #26",
        1,
    )
    with pytest.raises(
        AssertionError, match="shared-position roadmap classification drift"
    ):
        _assert_consistent(mutated, context)


def test_current_open_queue_counts_match_consumers() -> None:
    roadmap, _ = _load_documents()
    v88 = {
        ticket: metadata
        for ticket, metadata in _roadmap_tickets(roadmap).items()
        if metadata.kind == "v88"
    }
    assert len(v88) == 15
    assert len({metadata.merge_position for metadata in v88.values()}) == 14
    phrase = "fifteen open v88 ticket entries across fourteen open merge positions"
    for path in (DOCS_INDEX, ARCH_AUDIT):
        assert phrase in path.read_text(encoding="utf-8").replace("**", "").lower()
    roadmap_phrase = (
        "fourteen open merge positions carrying fifteen open ticket entries"
    )
    assert roadmap_phrase in roadmap.replace("**", "").lower()
