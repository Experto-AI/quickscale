"""Keep the v88 open-ticket context page covering the roadmap's open tickets.

The roadmap is the sole home for every schedulable fact — band, tier, worktree, merge
position, dependencies, slot ownership, validation-station status. The context page
restates none of them, so there is nothing for the two documents to disagree about.
What remains checkable, and is checked here, is:

* coverage — one context section per open roadmap ticket, and no orphan sections;
* no prose in a context section claiming a roadmap-open dependency is already closed.
"""

from __future__ import annotations

import re
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
SECTION_RE = re.compile(r"^## (SA\d+[^\n]*)$", re.MULTILINE)

# Sections that mention several tickets without being any one ticket's home.
AUXILIARY_SECTIONS = frozenset({"SA160 / SA161 sequencing note"})


def _roadmap_open_tickets(text: str) -> dict[str, frozenset[str]]:
    """Map each open roadmap ticket to the tickets it declares as dependencies."""
    unsupported = sorted(
        match.group(1)
        for match in TICKET_ENTRY_RE.finditer(text)
        if not (
            OPEN_ENTRY_RE.fullmatch(match.group(0))
            or CLOSED_ENTRY_RE.fullmatch(match.group(0))
        )
    )
    if unsupported:
        raise AssertionError(f"unsupported roadmap ticket entry shape: {unsupported}")

    tickets: dict[str, frozenset[str]] = {}
    for match in OPEN_ENTRY_RE.finditer(text):
        ticket = match.group(1)
        if ticket in tickets:
            raise AssertionError(f"duplicate open roadmap ticket: {ticket}")
        deps = re.search(r"\bdeps:\s*(.*?)(?:\s*[·—]|`|$)", match.group(0))
        if not deps:
            raise AssertionError(f"missing roadmap dependency metadata: {ticket}")
        text_after = deps.group(1).strip()
        tickets[ticket] = (
            frozenset()
            if re.match(r"none\b", text_after, re.IGNORECASE)
            else frozenset(TICKET_RE.findall(text_after))
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
    roadmap = _roadmap_open_tickets(roadmap_text)
    sections = _context_sections(context_text)

    if set(sections) != set(roadmap):
        raise AssertionError(
            "roadmap/current-context ticket coverage drift: "
            f"missing={sorted(set(roadmap) - set(sections))}, "
            f"unexpected={sorted(set(sections) - set(roadmap))}"
        )

    for ticket, dependencies in roadmap.items():
        for dependency in dependencies:
            claim = _positive_closure_claim(sections[ticket], dependency)
            if claim:
                raise AssertionError(
                    f"{ticket} claims roadmap-open dependency {dependency} is closed: "
                    f"{claim.group(0)!r}"
                )


SCHEDULABLE_METADATA_RE = re.compile(r"`(?:Band|Post-v88)[^`\n]*\bdeps:[^`\n]*`")


def _load_documents() -> tuple[str, str]:
    return ROADMAP.read_text(encoding="utf-8"), CONTEXT.read_text(encoding="utf-8")


def test_v88_current_context_covers_roadmap_open_tickets() -> None:
    roadmap, context = _load_documents()
    _assert_consistent(roadmap, context)


def test_v88_context_restates_no_schedulable_roadmap_metadata() -> None:
    """The context page must not grow a second copy of the roadmap's classification rows."""
    _, context = _load_documents()
    restated = SCHEDULABLE_METADATA_RE.findall(context)
    assert not restated, (
        "current-context page restates roadmap classification metadata, which can drift: "
        f"{restated}"
    )


def test_v88_schedulable_metadata_restatement_is_expected_red_canary() -> None:
    _, context = _load_documents()
    mutated = context + "\n`Band B · Tier 1 · W2 · merge #11 · deps: SA167a`\n"

    assert SCHEDULABLE_METADATA_RE.findall(mutated)


def test_v88_missing_roadmap_open_ticket_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated_roadmap = (
        roadmap
        + "\n- [ ] **SA999 — expected-red coverage canary.** `Post-v88 · Tier 3 · deps: none`\n"
    )

    with pytest.raises(AssertionError, match="ticket coverage drift"):
        _assert_consistent(mutated_roadmap, context)


def test_v88_unexpected_current_context_ticket_is_expected_red_canary() -> None:
    roadmap, context = _load_documents()
    mutated_context = context + "\n## SA999 — unexpected expected-red canary\n\nbody\n"

    with pytest.raises(AssertionError, match="ticket coverage drift"):
        _assert_consistent(roadmap, mutated_context)


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
    mutated_roadmap = (
        roadmap
        + "\n- [ ] **SA995 — dependency-metadata canary.** `Post-v88 · Tier 3`\n"
    )

    with pytest.raises(
        AssertionError, match="missing roadmap dependency metadata: SA995"
    ):
        _assert_consistent(mutated_roadmap, context)


@pytest.mark.parametrize(
    "claim",
    ["SA151 is closed.", "SA151's regenerated migrations are now settled."],
)
def test_v88_positive_dependency_closure_claim_is_expected_red_canary(
    claim: str,
) -> None:
    roadmap, context = _load_documents()
    section = _context_sections(context)["SA142"]
    mutated_context = context.replace(section, section + f"\n{claim}\n", 1)

    with pytest.raises(AssertionError, match="claims roadmap-open dependency SA151"):
        _assert_consistent(roadmap, mutated_context)
