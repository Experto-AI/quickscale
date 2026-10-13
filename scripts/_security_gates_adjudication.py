"""
Suppression-ledger loading and finding adjudication for the security gates.

The adjudication contract is preserved from the pre-split
``check_security_gates`` module: every suppression for an executed scanner
must match exactly one finding, and an unmatched or double-matched entry is
an infrastructure failure rather than a silent pass.  Collaborators resolve
through the support sibling at call time (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import _security_gates_support as _support

SUPPRESSIONS_PATH = _support.ROOT / "scripts" / "security_suppressions.json"

SUPPRESSION_KEYS = frozenset(
    {
        "scanner",
        "finding_id",
        "project",
        "path",
        "package",
        "installed_version",
        "code_identity",
        "fingerprint",
        "owner",
        "rationale",
        "decision_ref",
        "expires",
    }
)


def _load_suppressions() -> list[dict[str, Any]]:
    try:
        text = SUPPRESSIONS_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise _support.GateError(f"could not read suppression ledger: {exc}") from exc
    document = _support.strict_json(text, source=str(SUPPRESSIONS_PATH))
    if (
        not isinstance(document, dict)
        or set(document) != {"schema_version", "description", "suppressions"}
        or document.get("schema_version") != 1
    ):
        raise _support.GateError("invalid suppression ledger schema")
    entries = document.get("suppressions")
    if not isinstance(entries, list):
        raise _support.GateError("suppression ledger must contain a list")
    seen: set[str] = set()
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or set(entry) - SUPPRESSION_KEYS
            or SUPPRESSION_KEYS - set(entry)
        ):
            raise _support.GateError("suppression entries have unknown or missing fields")
        if any(
            not isinstance(entry[key], str) or not entry[key].strip() for key in SUPPRESSION_KEYS
        ):
            raise _support.GateError("suppression entries may not contain empty fields")
        if entry["fingerprint"] in seen:
            raise _support.GateError(f"duplicate suppression fingerprint: {entry['fingerprint']}")
        seen.add(entry["fingerprint"])
        try:
            expiry = date.fromisoformat(entry["expires"])
        except ValueError as exc:
            raise _support.GateError(f"invalid suppression expiry: {entry['expires']}") from exc
        if expiry < date.today():
            raise _support.GateError(f"expired suppression: {entry['fingerprint']}")
        if entry["scanner"] not in {"trivy", "bandit"}:
            raise _support.GateError(f"unknown suppression scanner: {entry['scanner']}")
        if entry["finding_id"].lower() in {"all", "*", "any", "category"}:
            raise _support.GateError("broad scanner/category suppressions are forbidden")
    return entries


def _entry_matches_finding(finding: dict[str, Any], entry: dict[str, Any]) -> bool:
    """Return whether one suppression entry accounts for one finding."""
    if (
        finding["scanner"] != entry["scanner"]
        or finding["finding_id"] != entry["finding_id"]
        or finding["project"] != entry["project"]
        or finding["path"] != entry["path"]
    ):
        return False
    if finding["scanner"] == "trivy":
        if finding.get("package") != entry.get("package") or finding.get(
            "installed_version"
        ) != entry.get("installed_version"):
            return False
    else:
        if finding.get("code_identity") != entry.get("code_identity"):
            return False
    return finding["fingerprint"] == entry["fingerprint"]


def _adjudicate(
    findings: list[dict[str, Any]],
    *,
    executed_scanners: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    finding_scanners = {finding["scanner"] for finding in findings}
    if not finding_scanners <= executed_scanners:
        raise _support.GateError("findings include a scanner that was not executed")
    suppressions = [
        entry for entry in _load_suppressions() if entry["scanner"] in executed_scanners
    ]
    matches: dict[str, int] = {entry["fingerprint"]: 0 for entry in suppressions}
    unsuppressed: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for finding in findings:
        candidates = [entry for entry in suppressions if _entry_matches_finding(finding, entry)]
        if len(candidates) == 1:
            matches[candidates[0]["fingerprint"]] += 1
            suppressed.append(finding)
        else:
            unsuppressed.append(finding)
    stale = [fingerprint for fingerprint, count in matches.items() if count != 1]
    if stale:
        raise _support.GateError(
            f"suppression cardinality failure (zero or multiple matches): {', '.join(stale)}"
        )
    return unsuppressed, suppressed
