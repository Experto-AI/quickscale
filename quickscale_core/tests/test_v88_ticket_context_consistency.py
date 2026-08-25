"""Keep the v88 open-ticket context page covering the roadmap's open tickets.

The roadmap is the sole home for formal schedulable classification rows — band, tier,
worktree, merge position, dependencies, slot ownership, validation-station status. The
context page may retain conceptual rationale for those relationships but not a second current
classification. What remains checkable, and is checked here, is:

* coverage — one context section per open roadmap ticket, and no orphan sections;
* no copied roadmap classification row;
* no prose in a context section claiming a roadmap-open dependency is already closed.
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
    r"^\s*- \[ \] \*\*(SA\d+[a-z]?)\b.*?`((?:Band|Post-v88)[^`]*)`", re.MULTILINE
)
SECTION_RE = re.compile(r"^## (SA\d+[^\n]*)$", re.MULTILINE)

# Sections that mention several tickets without being any one ticket's home.
AUXILIARY_SECTIONS = frozenset({"SA160 / SA161 sequencing note"})

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
        ticket: sorted(metadata.dependencies - open_tickets)
        for ticket, metadata in tickets.items()
        if metadata.dependencies - open_tickets
    }
    if unknown_dependencies:
        raise AssertionError(
            f"roadmap dependencies do not name open tickets: {unknown_dependencies}"
        )
    return tickets


def _context_sections(text: str) -> dict[str, str]:
    """Map each ticket named in a context heading to that heading's section body."""
    matches = list(SECTION_RE.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group(1)
        if title in AUXILIARY_SECTIONS:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.start() : end]
        # A heading may name several tickets when they share one conceptual section.
        # Only the part before the em-dash names them; the prose half may cite others.
        named = TICKET_RE.findall(title.split("—")[0])
        if not named:
            raise AssertionError(f"unclassified current-context section: {title}")
        for ticket in named:
            if ticket in sections:
                raise AssertionError(
                    f"duplicate current-context ticket section: {ticket}"
                )
            sections[ticket] = body
    return sections


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

    if set(sections) != set(roadmap):
        raise AssertionError(
            "roadmap/current-context ticket coverage drift: "
            f"missing={sorted(set(roadmap) - set(sections))}, "
            f"unexpected={sorted(set(sections) - set(roadmap))}"
        )

    expected_shared_groups = set(SHARED_POSITION_GROUPS)
    actual_shared_groups = _shared_position_groups(roadmap)
    if actual_shared_groups != expected_shared_groups:
        raise AssertionError(
            "shared-position roadmap classification drift: "
            f"expected={sorted(map(sorted, expected_shared_groups))}, "
            f"actual={sorted(map(sorted, actual_shared_groups))}"
        )

    for ticket, metadata in roadmap.items():
        for dependency in metadata.dependencies:
            claim = _positive_closure_claim(sections[ticket], dependency)
            if claim:
                raise AssertionError(
                    f"{ticket} claims roadmap-open dependency {dependency} is closed: "
                    f"{claim.group(0)!r}"
                )


CLASSIFICATION_ROW_RE = re.compile(r"`(?:Band|Post-v88)[^`\n]*\bdeps:[^`\n]*`")


def _load_documents() -> tuple[str, str]:
    return ROADMAP.read_text(encoding="utf-8"), CONTEXT.read_text(encoding="utf-8")


def _number_word(value: int) -> str:
    words = {14: "fourteen", 15: "fifteen"}
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
    assert (len(v88), len(positions)) == (15, 14)
    assert "SA151" not in roadmap
    assert 3 not in positions
    assert re.search(r"Positions [^\n]*#3[^\n]*retired", roadmap_text)
    assert not re.search(r"^## SA151\b", context_text, re.MULTILINE)

    assert v88["SA142"].dependencies == frozenset()
    assert v88["SA164"].dependencies == frozenset({"SA166"})
    assert roadmap["SA152"].dependencies == frozenset()
    assert v88["SA135"].dependencies == frozenset({"SA142"})
    assert v88["SA163"].dependencies == frozenset({"SA135"})
    assert "use the same twelve databases" in roadmap_text
    assert re.search(
        r"own all twelve databases first.*?ownership must be restored",
        roadmap_text,
        re.DOTALL,
    )

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
    assert Counter(severities) == Counter({"S3": 1, "S4": 1})
    assert re.search(
        r"S1 \*\*0\*\*.*S2 \*\*0\*\*.*S3 \*\*1\*\*.*S4 \*\*1\*\*.*Total 2 open",
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


def test_v88_context_restates_no_roadmap_classification_rows() -> None:
    _, context = _load_documents()
    restated = CLASSIFICATION_ROW_RE.findall(context)
    assert not restated, (
        "current-context page restates roadmap classification metadata, which can drift: "
        f"{restated}"
    )


def test_v88_classification_row_restatement_is_expected_red_canary() -> None:
    _, context = _load_documents()
    mutated = context + "\n`Band B · Tier 1 · W2 · merge #11 · deps: SA167a`\n"

    assert CLASSIFICATION_ROW_RE.findall(mutated)


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


def test_v88_checked_roadmap_entry_is_excluded_from_open_context() -> None:
    roadmap, context = _load_documents()
    mutated_roadmap = (
        roadmap + "\n- [x] **SA997 — closed-ticket exclusion canary.** "
        "`Post-v88 · Tier 3 · deps: none`\n"
    )

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
    mutated_context = context + "\n## SA999 — unexpected expected-red canary\n\nbody\n"

    with pytest.raises(AssertionError, match="ticket coverage drift"):
        _assert_consistent(roadmap, mutated_context)


def test_v88_positive_dependency_closure_claim_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    dependency_ticket = next(
        ticket
        for ticket, metadata in _roadmap_tickets(roadmap).items()
        if metadata.dependencies
    )
    dependency = next(iter(_roadmap_tickets(roadmap)[dependency_ticket].dependencies))
    section = _context_sections(context)[dependency_ticket]
    claim_templates = (
        "{dependency} is closed.",
        "{dependency}'s prerequisite is now settled.",
    )
    for claim_template in claim_templates:
        claim = claim_template.format(dependency=dependency)
        mutated_context = context.replace(section, section + f"\n{claim}\n", 1)

        with pytest.raises(
            AssertionError,
            match=rf"claims roadmap-open dependency {re.escape(dependency)}",
        ):
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
