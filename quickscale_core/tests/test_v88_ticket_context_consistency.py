"""Keep the v88 open-ticket context synchronized with the roadmap."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
ROADMAP = ROOT / "docs/technical/roadmap.md"
CONTEXT = ROOT / "docs/technical/v88_ticket_context.md"
TICKET_RE = re.compile(r"\bSA\d+[a-z]?\b")
TICKET_ENTRY_RE = re.compile(
    r"^\s*-\s+\[[^\]]*\]\s+\*\*(SA\d+[a-z]?)\b[^\n]*$", re.MULTILINE
)
OPEN_ENTRY_RE = re.compile(r"^\s*- \[ \] \*\*(SA\d+[a-z]?)\b[^\n]*$", re.MULTILINE)
CLOSED_ENTRY_RE = re.compile(r"^\s*- \[x\] \*\*(SA\d+[a-z]?)\b[^\n]*$", re.MULTILINE)
OPEN_TICKET_RE = re.compile(
    r"^\s*- \[ \] \*\*(SA\d+[a-z]?)\b.*?`((?:Band|Post-v88)[^`]*)`", re.MULTILINE
)
SECTION_RE = re.compile(r"^## (SA\d+[^\n]*)$", re.MULTILINE)

UMBRELLA_TITLE = "SA167a / SA167b / SA167c / SA167d — module wiring standardization"
UMBRELLA_MEMBERS = frozenset({"SA167a", "SA167b", "SA167c", "SA167d"})
AUXILIARY_MULTI_TICKET_SECTIONS = frozenset({"SA160 / SA161 sequencing note"})
RETAINED_CLOSED_TICKETS = frozenset({"SA162"})

# SA135 and SA163 share one merge position, but remain separately enumerable roadmap entries.
SHARED_POSITION_GROUPS = (frozenset({"SA135", "SA163"}),)


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
    entry_matches = list(TICKET_ENTRY_RE.finditer(text))
    entry_tickets = [match.group(1) for match in entry_matches]
    duplicate_entries = sorted(
        ticket for ticket, count in Counter(entry_tickets).items() if count > 1
    )
    if duplicate_entries:
        raise AssertionError(f"duplicate roadmap ticket entry: {duplicate_entries}")

    unsupported = sorted(
        match.group(1)
        for match in entry_matches
        if not (
            OPEN_ENTRY_RE.fullmatch(match.group(0))
            or CLOSED_ENTRY_RE.fullmatch(match.group(0))
        )
    )
    if unsupported:
        raise AssertionError(f"unsupported roadmap ticket entry shape: {unsupported}")

    closed_tickets = set(CLOSED_ENTRY_RE.findall(text))
    if closed_tickets != set(RETAINED_CLOSED_TICKETS):
        raise AssertionError(
            "checked roadmap tickets do not match the retained completion marker: "
            f"expected={sorted(RETAINED_CLOSED_TICKETS)}, "
            f"actual={sorted(closed_tickets)}"
        )

    open_entries = OPEN_ENTRY_RE.findall(text)
    duplicates = sorted(
        ticket for ticket, count in Counter(open_entries).items() if count > 1
    )
    if duplicates:
        raise AssertionError(f"duplicate open roadmap ticket: {duplicates}")

    parsed_tickets = [match.group(1) for match in OPEN_TICKET_RE.finditer(text)]
    unparseable = sorted(set(open_entries) - set(parsed_tickets))
    if unparseable:
        raise AssertionError(
            f"open roadmap tickets have unparseable classification metadata: {unparseable}"
        )

    tickets: dict[str, TicketMetadata] = {}
    for match in OPEN_TICKET_RE.finditer(text):
        ticket, metadata = match.groups()
        if ticket in tickets:
            raise AssertionError(f"duplicate open roadmap ticket: {ticket}")
        if not re.search(r"\bdeps:\s*", metadata):
            raise AssertionError(f"missing roadmap dependency metadata: {ticket}")
        kind = "post-v88" if "Post-v88" in metadata else "v88"
        tickets[ticket] = TicketMetadata(
            dependencies=_dependencies(metadata),
            kind=kind,
            merge_position=_merge_position(metadata, kind, ticket),
        )
    open_tickets = set(tickets)
    unknown_dependencies = {
        ticket: sorted(metadata.dependencies - open_tickets - closed_tickets)
        for ticket, metadata in tickets.items()
        if metadata.dependencies - open_tickets - closed_tickets
    }
    if unknown_dependencies:
        raise AssertionError(
            f"roadmap dependencies do not name open tickets: {unknown_dependencies}"
        )
    return tickets


def _section_blocks(text: str) -> list[tuple[str, str]]:
    matches = list(SECTION_RE.finditer(text))
    return [
        (
            match.group(1),
            text[
                match.start() : (
                    matches[index + 1].start()
                    if index + 1 < len(matches)
                    else len(text)
                )
            ],
        )
        for index, match in enumerate(matches)
    ]


def _context_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for title, section in _section_blocks(text):
        if title == UMBRELLA_TITLE or title in AUXILIARY_MULTI_TICKET_SECTIONS:
            continue
        title_ticket = re.match(r"^(SA\d+[a-z]?)\b", title)
        if not title_ticket:
            raise AssertionError(f"unclassified current-context section: {title}")
        ticket = title_ticket.group(1)
        if ticket in sections:
            raise AssertionError(f"duplicate current-context ticket section: {ticket}")
        sections[ticket] = section
    return sections


def _umbrella_section(text: str) -> str:
    sections = [
        section for title, section in _section_blocks(text) if title == UMBRELLA_TITLE
    ]
    if len(sections) != 1:
        raise AssertionError(
            f"expected exactly one current-context umbrella section, found {len(sections)}"
        )
    return sections[0]


def _direct_context_metadata(ticket: str, section: str) -> TicketMetadata:
    match = re.search(r"`((?:Band|Post-v88)[^`]*)`", section)
    if not match:
        raise AssertionError(
            f"missing current-context classification metadata: {ticket}"
        )
    metadata = match.group(1)
    if not re.search(r"\bdeps:\s*", metadata):
        raise AssertionError(f"missing current-context dependency metadata: {ticket}")
    kind = "post-v88" if "Post-v88" in metadata else "v88"
    return TicketMetadata(
        _dependencies(metadata), kind, _merge_position(metadata, kind, ticket)
    )


def _umbrella_metadata(section: str) -> dict[str, TicketMetadata]:
    rows: dict[str, TicketMetadata] = {}
    for ticket, merge_text, dependency_text in re.findall(
        r"^\| (SA\d+[a-z]?) \| #(\d+) \| ([^|]+) \|", section, re.MULTILINE
    ):
        if ticket in rows:
            raise AssertionError(f"duplicate umbrella classification row: {ticket}")
        rows[ticket] = TicketMetadata(
            frozenset(TICKET_RE.findall(dependency_text)), "v88", int(merge_text)
        )
    return rows


def _context_metadata(
    sections: dict[str, str], umbrella_section: str
) -> dict[str, TicketMetadata]:
    metadata: dict[str, TicketMetadata] = {}
    for ticket, section in sections.items():
        metadata[ticket] = _direct_context_metadata(ticket, section)
    umbrella_rows = _umbrella_metadata(umbrella_section)
    if set(umbrella_rows) != set(UMBRELLA_MEMBERS):
        raise AssertionError(
            "umbrella classification rows do not match the declared members: "
            f"expected={sorted(UMBRELLA_MEMBERS)}, actual={sorted(umbrella_rows)}"
        )
    metadata.update(umbrella_rows)
    return metadata


def _shared_position_groups(
    tickets: dict[str, TicketMetadata],
) -> set[frozenset[str]]:
    by_position: defaultdict[int, set[str]] = defaultdict(set)
    for ticket, metadata in tickets.items():
        if metadata.merge_position is not None:
            by_position[metadata.merge_position].add(ticket)
    return {frozenset(group) for group in by_position.values() if len(group) > 1}


def _positive_closure_claim(section: str, dependency: str) -> re.Match[str] | None:
    direct = re.search(
        rf"\b{re.escape(dependency)}\b\s+(?:(?:is|was|remains)\s+)?"
        r"(?:closed|satisfied|settled|complete)\b",
        section,
        re.IGNORECASE,
    )
    if direct:
        return direct
    return re.search(
        rf"\b{re.escape(dependency)}'s\b[^.\n]{{0,80}}\b"
        r"(?:is|was|are|were|remains|has been)\s+(?:now\s+)?"
        r"(?:closed|satisfied|settled|complete)\b",
        section,
        re.IGNORECASE,
    )


def _assert_consistent(roadmap_text: str, context_text: str) -> None:
    roadmap = _roadmap_tickets(roadmap_text)
    sections = _context_sections(context_text)
    umbrella_section = _umbrella_section(context_text)
    context = _context_metadata(sections, umbrella_section)

    closed_roadmap_tickets = set(CLOSED_ENTRY_RE.findall(roadmap_text))
    context_tickets = set(context) - closed_roadmap_tickets
    if context_tickets != set(roadmap):
        raise AssertionError(
            "roadmap/current-context ticket coverage drift: "
            f"missing={sorted(set(roadmap) - context_tickets)}, "
            f"unexpected={sorted(context_tickets - set(roadmap))}"
        )

    expected_shared_groups = set(SHARED_POSITION_GROUPS)
    actual_shared_groups = _shared_position_groups(roadmap)
    if actual_shared_groups != expected_shared_groups:
        raise AssertionError(
            "shared-position roadmap classification drift: "
            f"expected={sorted(map(sorted, expected_shared_groups))}, "
            f"actual={sorted(map(sorted, actual_shared_groups))}"
        )
    if _shared_position_groups(context) != expected_shared_groups:
        raise AssertionError("shared-position current-context classification drift")

    status_sections = sections | {
        ticket: umbrella_section for ticket in UMBRELLA_MEMBERS
    }
    for ticket, expected in roadmap.items():
        if context[ticket] != expected:
            raise AssertionError(
                f"metadata drift for {ticket}: roadmap={expected}, "
                f"current-context={context[ticket]}"
            )

        for dependency in expected.dependencies:
            if dependency in closed_roadmap_tickets:
                continue
            positive_closure = _positive_closure_claim(
                status_sections[ticket], dependency
            )
            if positive_closure:
                raise AssertionError(
                    f"{ticket} claims roadmap-open dependency {dependency} is closed: "
                    f"{positive_closure.group(0)!r}"
                )


def _load_documents() -> tuple[str, str]:
    return ROADMAP.read_text(encoding="utf-8"), CONTEXT.read_text(encoding="utf-8")


def test_v88_current_context_matches_roadmap_open_tickets_and_dependencies() -> None:
    roadmap, context = _load_documents()
    _assert_consistent(roadmap, context)


def test_v88_missing_roadmap_open_ticket_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated_roadmap = (
        roadmap
        + "\n- [ ] **SA999 — expected-red coverage canary.** `Post-v88 · Tier 3 · deps: none`\n"
    )

    with pytest.raises(AssertionError, match="ticket coverage drift"):
        _assert_consistent(mutated_roadmap, context)


def test_v88_unparseable_open_roadmap_ticket_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated_roadmap = (
        roadmap
        + "\n- [ ] **SA998 — malformed expected-red canary.** `Tier 3 · deps: none`\n"
    )

    with pytest.raises(AssertionError, match="unparseable classification metadata"):
        _assert_consistent(mutated_roadmap, context)


def test_v88_unexpected_checked_roadmap_entry_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated_roadmap = (
        roadmap + "\n- [x] **SA997 — closed-ticket exclusion canary.** "
        "`Post-v88 · Tier 3 · deps: none`\n"
    )

    with pytest.raises(AssertionError, match="checked roadmap tickets"):
        _assert_consistent(mutated_roadmap, context)


def test_v88_unsupported_roadmap_entry_shape_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated_roadmap = (
        roadmap + "\n- [-] **SA996 — unsupported expected-red canary.** "
        "`Post-v88 · Tier 3 · deps: none`\n"
    )

    with pytest.raises(AssertionError, match="unsupported roadmap ticket entry shape"):
        _assert_consistent(mutated_roadmap, context)


def test_v88_missing_roadmap_dependency_metadata_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated_roadmap = roadmap.replace(
        "merge #15 · deps: SA135 — executes inside SA135",
        "merge #15 — executes inside SA135",
        1,
    )
    assert mutated_roadmap != roadmap

    with pytest.raises(
        AssertionError, match="missing roadmap dependency metadata: SA163"
    ):
        _assert_consistent(mutated_roadmap, context)


def test_v88_unknown_roadmap_dependency_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated_roadmap = roadmap.replace("deps: SA135 —", "deps: SA999 —", 1)
    assert mutated_roadmap != roadmap

    with pytest.raises(AssertionError, match="dependencies do not name open tickets"):
        _assert_consistent(mutated_roadmap, context)


def test_v88_unexpected_current_context_ticket_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated_context = (
        context + "\n## SA999 — unexpected expected-red canary\n\n"
        "`Post-v88 · Tier 3 · deps: none`\n"
    )

    with pytest.raises(AssertionError, match="ticket coverage drift"):
        _assert_consistent(roadmap, mutated_context)


def test_v88_dependency_status_contradiction_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    dependency_ticket = next(
        ticket
        for ticket, metadata in _roadmap_tickets(roadmap).items()
        if metadata.dependencies
    )
    sections = _context_sections(context)
    if dependency_ticket not in sections:
        pytest.fail(
            f"canary selected an umbrella ticket without a direct metadata row: {dependency_ticket}"
        )

    section = sections[dependency_ticket]
    metadata = re.search(r"`[^`]*\bdeps:\s*[^`]+`", section)
    assert metadata is not None
    mutated_metadata = re.sub(
        r"\bdeps:\s*[^·—`]+",
        "deps: none (expected-red canary)",
        metadata.group(0),
        count=1,
    )
    mutated_context = context.replace(metadata.group(0), mutated_metadata, 1)

    with pytest.raises(AssertionError, match="metadata drift"):
        _assert_consistent(roadmap, mutated_context)


@pytest.mark.parametrize(
    "claim",
    ["SA151 is closed.", "SA151's regenerated migrations are now settled."],
)
def test_v88_positive_dependency_closure_claim_is_expected_red_canary(
    claim: str,
) -> None:
    roadmap, context = _load_documents()
    sections = _context_sections(context)
    section = sections["SA142"]
    mutated_context = context.replace(section, section + f"\n{claim}\n", 1)

    with pytest.raises(AssertionError, match="claims roadmap-open dependency SA151"):
        _assert_consistent(roadmap, mutated_context)


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
