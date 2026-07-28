#!/usr/bin/env python3
"""
SA121 — merge-base baseline monotonicity gate.

Compares every ceiling in the current ``quality_baseline.json`` against the
merge-base blob from Git and rejects increases unless covered by a structured,
time-bounded waiver in ``quality_waivers.json``.

Exit codes
----------
0 — no violations: current <= base for every compared value, or every
    increase is covered by an active, well-formed waiver.
1 — policy violation: at least one increase without a valid waiver.
2 — schema error, Git failure, merge-base resolution failure, or other
    prerequisite problem.

Output
------
Atomically writes ``.quickscale/quality_baseline_policy.json`` with the full
comparison result, violation list, waiver evaluation, and final verdict.
"""

from __future__ import annotations

import argparse
import json
import os
import re as _re
import subprocess
import sys
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_YYYY_MM_DD_RE = _re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

# Canonical source labels for error envelopes
_SOURCE_MERGE_BASE = "merge_base_baseline"
_SOURCE_CURRENT = "current_baseline"
_SOURCE_WAIVER = "waiver_ledger"
_SOURCE_GIT = "git"
_SOURCE_MAIN = "main"


class SchemaValidationError(RuntimeError):
    """Structured schema validation error carrying source label and JSON path."""

    def __init__(self, source: str, path: str, message: str) -> None:
        self.source = source
        self.path = path
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# Path validation (CR-003: strict safe repo-relative POSIX validator)
# ---------------------------------------------------------------------------


def _validate_repo_relative_path(path: str, source: str, json_path: str) -> None:
    """
    Validate that *path* is a strict safe repo-relative POSIX path.

    Rejects absolute paths, Windows backslashes/drive letters, empty/dot/dotdot
    segments, repeated separators, leading/trailing whitespace, and surrogate
    or control characters.

    Raises ``SchemaValidationError`` on the first violation.
    """
    if not isinstance(path, str) or not path:
        raise SchemaValidationError(
            source,
            json_path,
            f"{json_path} must be a non-empty string",
        )
    if path.startswith("/"):
        raise SchemaValidationError(
            source,
            json_path,
            f"{json_path}={path!r} must be repo-relative, not absolute",
        )
    if "\\" in path:
        raise SchemaValidationError(
            source,
            json_path,
            f"{json_path}={path!r} must use POSIX separators, not backslashes",
        )
    if _re.match(r"^[A-Za-z]:", path):
        raise SchemaValidationError(
            source,
            json_path,
            f"{json_path}={path!r} must not contain Windows drive letter",
        )
    # Check each segment
    for segment in path.split("/"):
        if segment in ("", ".", ".."):
            raise SchemaValidationError(
                source,
                json_path,
                f"{json_path}={path!r} must not contain empty, dot, or dotdot segments",
            )
    if "//" in path:
        raise SchemaValidationError(
            source,
            json_path,
            f"{json_path}={path!r} must not contain repeated separators",
        )
    stripped = path.strip()
    if path != stripped:
        raise SchemaValidationError(
            source,
            json_path,
            f"{json_path}={path!r} must not contain leading or trailing whitespace",
        )
    # Reject every ASCII control character (including tab/newline), DEL,
    # and Unicode surrogate/category Cs (both high and low surrogates)
    for ch in path:
        code = ord(ch)
        if code < 0x20 or code == 0x7F or 0xD800 <= code <= 0xDFFF:
            raise SchemaValidationError(
                source,
                json_path,
                f"{json_path}={path!r} must not contain control, surrogate, or DEL characters",
            )


def _validate_free_text(text: str, source: str, json_path: str) -> None:
    """
    Validate that *text* contains no ASCII control characters, DEL, or surrogates.

    Raises ``SchemaValidationError`` on the first violating character.
    """
    if not isinstance(text, str) or not text:
        raise SchemaValidationError(
            source,
            json_path,
            f"{json_path} must be a non-empty string",
        )
    for ch in text:
        code = ord(ch)
        if code < 0x20 or code == 0x7F or 0xD800 <= code <= 0xDFFF:
            raise SchemaValidationError(
                source,
                json_path,
                f"{json_path}={text!r} must not contain control, surrogate, or DEL characters",
            )


def _parse_entry_key(entry_key: str) -> tuple[str, str]:
    """
    Parse a waiver ``entry_key`` into ``(section_prefix, remainder)``.

    Section-specific canonical syntax:

    - ``dead_code:allowed_messages:<msg>:multiplicity``
    - ``complexity:<safe-repo-path>::<nonempty-symbol>``
    - ``duplication:allowed_blocks``

    Returns ``(section, entry_key)`` where *section* is the validated prefix.
    Raises ``ValueError`` if the key does not match the section's canonical syntax,
    carries extra or missing separators, or contains an invalid repo path.
    """
    if entry_key.startswith("dead_code:allowed_messages:") and entry_key.endswith(":multiplicity"):
        # Extract the message part (between the prefix and suffix); must be nonempty
        msg = entry_key[len("dead_code:allowed_messages:") : -len(":multiplicity")]
        if not msg:
            raise ValueError(f"dead_code entry_key must have nonempty message: {entry_key!r}")
        # CR-003: free-text validate the message part
        _validate_free_text(
            msg,
            "waiver_ledger",
            f"entry_key dead_code message in {entry_key!r}",
        )
        return ("dead_code", entry_key)

    if entry_key.startswith("complexity:"):
        remainder = entry_key[len("complexity:") :]
        # Must contain exactly one ``::`` separator between path and symbol
        if "::" not in remainder:
            raise ValueError(
                f"complexity entry_key must contain '::' separator between "
                f"path and symbol: {entry_key!r}"
            )
        parts = remainder.split("::")
        if len(parts) != 2:
            raise ValueError(
                f"complexity entry_key must have exactly one '::' separator "
                f"(got {len(parts) - 1}): {entry_key!r}"
            )
        path_part, symbol_part = parts
        if not path_part:
            raise ValueError(f"complexity entry_key path must be nonempty: {entry_key!r}")
        if not symbol_part:
            raise ValueError(f"complexity entry_key symbol must be nonempty: {entry_key!r}")
        # Validate the repo-relative path part via the path validator
        _validate_repo_relative_path(
            path_part,
            "waiver_ledger",
            f"entry_key path component in {entry_key!r}",
        )
        # CR-003: free-text validate the symbol part
        _validate_free_text(
            symbol_part,
            "waiver_ledger",
            f"entry_key symbol component in {entry_key!r}",
        )
        return ("complexity", entry_key)

    if entry_key == "duplication:allowed_blocks":
        return ("duplication", entry_key)

    raise ValueError(f"Unknown entry_key prefix or format: {entry_key!r}")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_BASELINE = _REPO_ROOT / "scripts" / "quality_baseline.json"
_DEFAULT_WAIVERS = _REPO_ROOT / "scripts" / "quality_waivers.json"
_OUTPUT_DIR = _REPO_ROOT / ".quickscale"
_OUTPUT_FILE = _OUTPUT_DIR / "quality_baseline_policy.json"
_CANONICAL_BASELINE_REPO_PATH = "scripts/quality_baseline.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path | None = None) -> str:
    """Run a git command and return stdout stripped."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or _REPO_ROOT),
        timeout=30,
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {msg}")
    return result.stdout.strip()


def _git_show(commit: str, path: str) -> str | None:
    """Return file content from a Git commit, or None if the path does not exist at that commit."""
    try:
        return _git(["show", f"{commit}:{path}"])
    except RuntimeError as exc:
        # "fatal: path '...' does not exist" or "exists on disk, but not in"
        msg = str(exc)
        if "does not exist" in msg or "not found" in msg or "exists on disk" in msg:
            return None
        raise


def _resolve_merge_base(base_ref: str | None) -> str:
    """
    Resolve the merge-base commit hash using the precedence chain.

    Precedence:
        1. ``--base-ref`` CLI argument
        2. ``QUALITY_BASELINE_BASE_REF`` env var
        3. ``GITHUB_BASE_REF`` env var (origin/ then local)
        4. ``v87`` tag fallback

    Returns the full commit hash of the merge base.
    """
    ref: str | None = None

    if base_ref:
        ref = base_ref
    elif os.environ.get("QUALITY_BASELINE_BASE_REF"):
        ref = os.environ["QUALITY_BASELINE_BASE_REF"].strip()
    elif os.environ.get("GITHUB_BASE_REF"):
        github_ref = os.environ["GITHUB_BASE_REF"].strip()
        # Try origin/<branch> first, then local <branch>
        for candidate in (f"origin/{github_ref}", github_ref):
            try:
                _git(["rev-parse", "--verify", candidate])
                ref = candidate
                break
            except RuntimeError:
                continue
        if not ref:
            raise RuntimeError(
                f"GITHUB_BASE_REF={github_ref} is set but neither "
                f"origin/{github_ref} nor {github_ref} resolves locally"
            )

    if not ref:
        # Fallback to v87 tag
        ref = "v87"

    # Resolve to a commit hash
    ref_commit = _git(["rev-parse", "--verify", ref])

    # Compute merge base with HEAD
    merge_base = _git(["merge-base", ref_commit, "HEAD"])
    return merge_base


def _load_json(path: str | Path) -> dict[str, Any]:
    """Load and return a JSON file, or raise on error."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError) as exc:
        raise RuntimeError(f"Cannot load {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} must be a JSON object (got {type(data).__name__})")
    return data


def _validate_baseline_structure(
    data: dict[str, Any],
    source: str,
) -> dict[str, int]:
    """
    Validate that *data* is a well-formed quality baseline dict.

    Raises ``SchemaValidationError`` with ``source``, ``path``, and ``message``
    on the first structural violation.  This is BOTH the merge-base blob and
    the current file: every loaded baseline must pass this check before
    canonicalization.

    Returns validated ceiling indexes as ``dict[str, int]`` keyed by canonical
    key.  Never returns malformed defaults — exits 2 before returning if the
    data is structurally invalid.
    """
    if not isinstance(data, dict):
        raise SchemaValidationError(source, "", "must be a JSON object")

    schema = data.get("schema_version")
    if not _is_strict_int(schema):
        raise SchemaValidationError(
            source,
            "schema_version",
            f"schema_version must be a non-boolean integer (got {type(schema).__name__})",
        )
    if schema != 1:
        raise SchemaValidationError(
            source,
            "schema_version",
            f"unsupported schema_version {schema} (expected 1)",
        )

    indexes: dict[str, int] = {}

    # ---- dead_code ----
    dc = data.get("dead_code")
    if not isinstance(dc, dict):
        raise SchemaValidationError(
            source,
            "dead_code",
            f"missing or non-dict section 'dead_code' "
            f"(got {type(dc).__name__ if dc is not None else 'None'})",
        )
    dc_msgs = dc.get("allowed_messages")
    if not isinstance(dc_msgs, list):
        raise SchemaValidationError(
            source,
            "dead_code.allowed_messages",
            f"dead_code.allowed_messages must be a list "
            f"(got {type(dc_msgs).__name__ if dc_msgs is not None else 'None'})",
        )
    for i, m in enumerate(dc_msgs):
        if not isinstance(m, str) or not m:
            raise SchemaValidationError(
                source,
                f"dead_code.allowed_messages[{i}]",
                f"dead_code.allowed_messages[{i}] must be a non-empty string "
                f"(got {type(m).__name__ if m is not None else 'None'})",
            )
        _validate_free_text(
            m,
            source,
            f"dead_code.allowed_messages[{i}]",
        )
    from collections import Counter

    for msg, count in Counter(dc_msgs).items():
        indexes[f"dead_code:allowed_messages:{msg}:multiplicity"] = count

    # ---- complexity ----
    cf = data.get("complexity")
    if not isinstance(cf, dict):
        raise SchemaValidationError(
            source,
            "complexity",
            f"missing or non-dict section 'complexity' "
            f"(got {type(cf).__name__ if cf is not None else 'None'})",
        )
    cf_fns = cf.get("allowed_functions")
    if not isinstance(cf_fns, dict):
        raise SchemaValidationError(
            source,
            "complexity.allowed_functions",
            f"complexity.allowed_functions must be a dict "
            f"(got {type(cf_fns).__name__ if cf_fns is not None else 'None'})",
        )
    valid_complexity_types = {"function", "method", "class"}
    for ck, entry in cf_fns.items():
        if not isinstance(ck, str) or not ck:
            raise SchemaValidationError(
                source,
                "complexity.allowed_functions",
                "complexity.allowed_functions key must be a non-empty string",
            )
        if not isinstance(entry, dict):
            raise SchemaValidationError(
                source,
                f"complexity.allowed_functions[{ck!r}]",
                f"complexity.allowed_functions[{ck!r}] must be a dict (got {type(entry).__name__})",
            )
        for field in ("file", "symbol"):
            val = entry.get(field)
            if not isinstance(val, str) or not val:
                raise SchemaValidationError(
                    source,
                    f"complexity.allowed_functions[{ck!r}].{field}",
                    f"complexity.allowed_functions[{ck!r}].{field} must be a non-empty string",
                )
        # CR-003: validate repo-relative path for complexity file field
        _validate_repo_relative_path(
            entry["file"],
            source,
            f"complexity.allowed_functions[{ck!r}].file",
        )
        # CR-003: free-text validate symbol
        _validate_free_text(
            entry["symbol"],
            source,
            f"complexity.allowed_functions[{ck!r}].symbol",
        )
        # CR-003: complexity map key must equal exact file::symbol
        expected_key = f"{entry['file']}::{entry['symbol']}"
        if ck != expected_key:
            raise SchemaValidationError(
                source,
                "complexity.allowed_functions",
                (f"complexity key {ck!r} must equal file::symbol {expected_key!r}"),
            )
        typ = entry.get("type")
        if typ not in valid_complexity_types:
            raise SchemaValidationError(
                source,
                f"complexity.allowed_functions[{ck!r}].type",
                f"complexity.allowed_functions[{ck!r}].type "
                f"must be one of {sorted(valid_complexity_types)} "
                f"(got {typ!r})",
            )
        mc = entry.get("max_complexity")
        if not _is_strict_int(mc) or mc < 0:
            raise SchemaValidationError(
                source,
                f"complexity.allowed_functions[{ck!r}].max_complexity",
                f"complexity.allowed_functions[{ck!r}].max_complexity "
                f"must be a non-negative integer "
                f"(got {type(mc).__name__ if mc is not None else 'None'})",
            )
        indexes[f"complexity:{ck}"] = int(mc)

    # ---- large_files: RETIRED (SA125-DEC-001) ----
    # A pre-SA125 baseline (e.g. the merge-base side of the comparison) may still
    # carry the section. It is ignored, never indexed, so no LF key can enter the
    # monotonicity index from either side and no LF-RISE can ever be computed.
    # Rejecting a resurrected section is check_quality.sh's job, on the live
    # baseline only -- doing it here would break every run until the parent ages out.

    # ---- duplication ----
    dup = data.get("duplication")
    if not isinstance(dup, dict):
        raise SchemaValidationError(
            source,
            "duplication",
            f"missing or non-dict section 'duplication' "
            f"(got {type(dup).__name__ if dup is not None else 'None'})",
        )
    dup_blocks = dup.get("allowed_blocks")
    if not _is_strict_int(dup_blocks) or dup_blocks < 0:
        raise SchemaValidationError(
            source,
            "duplication.allowed_blocks",
            f"duplication.allowed_blocks must be a non-negative integer "
            f"(got {type(dup_blocks).__name__ if dup_blocks is not None else 'None'})",
        )
    indexes["duplication:allowed_blocks"] = int(dup_blocks)

    # Validate allowed_block_identities if present
    if "allowed_block_identities" in dup:
        identities = dup["allowed_block_identities"]
        if not isinstance(identities, list):
            raise SchemaValidationError(
                source,
                "duplication.allowed_block_identities",
                f"duplication.allowed_block_identities must be a list "
                f"(got {type(identities).__name__})",
            )
        if len(identities) != dup_blocks:
            raise SchemaValidationError(
                source,
                "duplication.allowed_block_identities",
                f"duplication.allowed_block_identities length "
                f"{len(identities)} != allowed_blocks {dup_blocks}",
            )
        for i, ident in enumerate(identities):
            if not isinstance(ident, str) or not ident:
                raise SchemaValidationError(
                    source,
                    f"duplication.allowed_block_identities[{i}]",
                    f"duplication.allowed_block_identities[{i}] must be a non-empty string",
                )

    return indexes


def _validate_waiver_ledger_structure(
    data: dict[str, Any],
    source: str,
) -> list[dict[str, Any]]:
    """
    Validate that *data* is a well-formed waiver ledger dict.

    Raises ``SchemaValidationError`` with ``source`` and ``path`` on the first
    structural violation.  Returns the validated waivers list on success.
    """
    if not isinstance(data, dict):
        raise SchemaValidationError(source, "", "must be a JSON object")

    schema = data.get("schema_version")
    if not _is_strict_int(schema):
        raise SchemaValidationError(
            source, "schema_version", "schema_version must be a non-boolean integer"
        )
    if schema != 1:
        raise SchemaValidationError(
            source, "schema_version", f"unsupported schema_version {schema} (expected 1)"
        )

    # description is optional; validate it if present
    if "description" in data:
        desc = data["description"]
        if not isinstance(desc, str) or not desc:
            raise SchemaValidationError(
                source, "description", "description must be a non-empty string when present"
            )

    waivers = data.get("waivers")
    if not isinstance(waivers, list):
        raise SchemaValidationError(
            source,
            "waivers",
            f'"waivers" must be a list '
            f"(got {type(waivers).__name__ if waivers is not None else 'None'})",
        )

    for i, entry in enumerate(waivers):
        if not isinstance(entry, dict):
            raise SchemaValidationError(
                source,
                f"waivers[{i}]",
                f"waiver at index {i} must be a JSON object (got {type(entry).__name__})",
            )

    return waivers


def _get_decision_anchors(path: Path) -> set[str]:
    """
    Return the set of all anchor IDs found in *path*.

    Recognises Markdown ``{#anchor-name}`` syntax and HTML
    ``<a id="anchor-name">`` syntax.
    """
    anchors: set[str] = set()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return anchors

    # Markdown heading anchors: {#anchor-name}
    for m in __import__("re").finditer(r"\{#([^}]+)\}", text):
        anchors.add(m.group(1))

    # HTML anchor tags: <a id="anchor-name"> or <a id='anchor-name'>
    for m in __import__("re").finditer(
        r"""<a\s+id=["']([^"']+)["']\s*>""",
        text,
    ):
        anchors.add(m.group(1))

    return anchors


def _load_json_from_git(commit: str, repo_path: str) -> dict[str, Any] | None:
    """Load a JSON file from a Git commit, or return None if it does not exist."""
    content = _git_show(commit, repo_path)
    if content is None:
        return None
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{repo_path} at {commit} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(
            f"{repo_path} at {commit} must be a JSON object (got {type(data).__name__})"
        )
    return data


def _load_waivers(path: str | Path) -> list[dict[str, Any]]:
    """Load waivers from a JSON file; missing file is treated as empty."""
    try:
        data = _load_json(path)
    except RuntimeError as exc:
        # Missing file is acceptable for initial rollout
        if "Cannot load" in str(exc) and not Path(path).exists():
            return []
        raise

    return _validate_waiver_ledger_structure(data, _SOURCE_WAIVER)


def _validate_waiver_row(
    waiver: dict[str, Any],
    index: int,
    now: date,
    known_anchors: set[str],
) -> str | None:
    """
    Validate a single waiver entry at *index*.

    Returns an error message if the waiver is invalid, or None if valid.
    The *index* is the 0-based position in the ledger array.
    """
    required = {
        "waiver_id",
        "entry_key",
        "base_ceiling",
        "ceiling",
        "owner",
        "reason",
        "expires_on",
        "decision_ref",
    }
    missing = required - set(waiver.keys())
    if missing:
        return f"waiver[{index}] missing required key(s): {', '.join(sorted(missing))}"

    waiver_id = waiver["waiver_id"]
    if not isinstance(waiver_id, str) or not waiver_id.strip():
        return f"waiver[{index}]: waiver_id must be a non-empty string"

    if not isinstance(waiver["entry_key"], str) or not waiver["entry_key"].strip():
        return f"waiver[{index}] ({waiver_id}): entry_key must be a non-empty string"

    # CR-003: validate entry_key format via _parse_entry_key before
    # lifecycle/matching — rejects malformed section-specific keys.
    # Catch both ValueError (key format) and SchemaValidationError (free-text
    # control/surrogate characters in message or symbol).
    try:
        _parse_entry_key(waiver["entry_key"])
    except (ValueError, SchemaValidationError) as exc:
        return f"waiver[{index}] ({waiver_id}): invalid entry_key — {exc}"

    for int_field in ("base_ceiling", "ceiling"):
        val = waiver.get(int_field)
        if not _is_strict_number(val) or val < 0:
            return f"waiver[{index}] ({waiver_id}): {int_field} must be a non-negative number"

    for str_field in ("owner", "reason", "decision_ref"):
        val = waiver.get(str_field)
        if not isinstance(val, str) or not val.strip():
            return f"waiver[{index}] ({waiver_id}): {str_field} must be a non-empty string"

    # Validate decision_ref resolves as an exact Markdown/HTML anchor
    ref_val = waiver["decision_ref"]
    if ref_val not in known_anchors:
        return (
            f"waiver[{index}] ({waiver_id}): decision_ref={ref_val!r} does not resolve "
            f"to any anchor in decisions.md"
        )

    # Validate expires_on is strict YYYY-MM-DD (format only — expiry
    # comparison against the current date is handled by the state machine)
    expires_raw = waiver["expires_on"]
    if not isinstance(expires_raw, str):
        return f"waiver[{index}] ({waiver_id}): expires_on must be a string in YYYY-MM-DD format"
    # CR-003: exact ASCII YYYY-MM-DD regex before parse
    if not _YYYY_MM_DD_RE.fullmatch(expires_raw):
        return (
            f"waiver[{index}] ({waiver_id}): expires_on={expires_raw!r} "
            f"does not match YYYY-MM-DD format"
        )
    try:
        date.fromisoformat(expires_raw)
    except ValueError:
        return f"waiver[{index}] ({waiver_id}): expires_on is not a valid YYYY-MM-DD date"

    return None


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

ComparisonResult = dict[str, Any]


def _is_strict_int(value: object) -> bool:
    """Return True if *value* is an ``int`` but not a ``bool``."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_strict_number(value: object) -> bool:
    """Return True if *value* is an ``int`` or ``float`` but not a ``bool``."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


_SECTION_ERROR_CODES: dict[str, str] = {
    "dead_code": "DC-MULT",
    "complexity": "CC-RISE",
    "duplication": "DP-RISE",
}

_SECTION_NAMES: dict[str, str] = {
    "dead_code": "dead_code",
    "complexity": "complexity",
    "duplication": "duplication",
}


def _compare_indexes(
    old_indexes: dict[str, int],
    new_indexes: dict[str, int],
) -> list[ComparisonResult]:
    """
    Compare validated ceiling indexes.

    Takes pre-validated ceiling indexes (from ``_validate_baseline_structure``)
    and returns a list of violations for every key whose value increased.
    Missing key in old is treated as 0 (any new value > 0 is an increase).
    """
    results: list[ComparisonResult] = []
    all_keys = sorted(set(old_indexes.keys()) | set(new_indexes.keys()))

    for ck in all_keys:
        old_val = old_indexes.get(ck, 0)
        new_val = new_indexes.get(ck, 0)

        if new_val > old_val:
            # Derive section and error code from canonical key prefix
            if ck.startswith("dead_code:"):
                section = "dead_code"
                error_code = "DC-MULT"
            elif ck.startswith("complexity:"):
                section = "complexity"
                error_code = "CC-RISE"
            elif ck.startswith("duplication:"):
                section = "duplication"
                error_code = "DP-RISE"
            else:
                section = "unknown"
                error_code = "UNKNOWN"

            results.append(
                {
                    "section": section,
                    "canonical_key": ck,
                    "old_value": old_val,
                    "new_value": new_val,
                    "error_code": error_code,
                }
            )

    return results


# ---------------------------------------------------------------------------
# Waiver matching (authoritative state machine)
# ---------------------------------------------------------------------------

# State precedence: each waiver row produces exactly one evaluation.
# Only the first matching state below applies.
_WaiverEval = dict[str, Any]


def _evaluate_violations(
    violations: list[ComparisonResult],
    waivers: list[dict[str, Any]],
    now: date,
    known_anchors: set[str],
    waiver_file: str = "",
) -> tuple[list[ComparisonResult], list[_WaiverEval]]:
    """
    Match violations against waivers using authoritative state precedence.

    State precedence (first match applies):
        1. Malformed       — per-row schema validation
        2. Duplicate ID    — waiver_id appears more than once (all copies)
        3. Duplicate key   — entry_key appears more than once (all copies)
        4. Expired         — expires_on < now (UTC date)
        5. Orphan          — no increase detected for this entry_key
        6. Stale base      — base_ceiling != merge-base value
        7. Over ceiling    — new_value > ceiling
        8. Active          — all checks pass

    CR-004: Duplicate inventory is built from EVERY row that exposes string
    waiver_id/entry_key dimensions, including otherwise-malformed rows.
    Malformed rows retain the malformed state but carry ``duplicate_kinds``
    metadata; otherwise-valid twins become ``duplicate``.

    Returns ``(unresolved_violations, waiver_evaluations)``.
    """
    total_waivers = len(waivers)
    evaluations: list[_WaiverEval | None] = [None] * total_waivers
    unresolved: list[ComparisonResult] = []

    # Derive section/error_code from a canonical key
    def _section_and_code(ck: str) -> tuple[str, str]:
        if ck.startswith("dead_code:"):
            return "dead_code", "DC-MULT"
        if ck.startswith("complexity:"):
            return "complexity", "CC-RISE"
        if ck.startswith("duplication:"):
            return "duplication", "DP-RISE"
        return "unknown", "UNKNOWN"

    # =================================================================
    # Phase 0 — Build full duplicate inventory from EVERY row.
    # Collect waiver_id and entry_key from all rows that expose them as
    # non-empty strings, including rows that are otherwise malformed.
    # =================================================================
    raw_waiver_ids: dict[str, list[int]] = {}
    raw_entry_keys: dict[str, list[int]] = {}

    for i, w in enumerate(waivers):
        wid = w.get("waiver_id")
        if isinstance(wid, str) and wid:
            raw_waiver_ids.setdefault(wid, []).append(i)
        ek = w.get("entry_key")
        if isinstance(ek, str) and ek:
            raw_entry_keys.setdefault(ek, []).append(i)

    # Compute duplicate sets from the full inventory
    dup_waiver_ids: set[str] = {wid for wid, idxs in raw_waiver_ids.items() if len(idxs) > 1}
    dup_entry_keys: set[str] = {ek for ek, idxs in raw_entry_keys.items() if len(idxs) > 1}

    # Map: is this row involved in a duplicate (any dimension)?
    def _row_dup_kinds(idx: int) -> list[str]:
        kinds: list[str] = []
        w = waivers[idx]
        wid = w.get("waiver_id")
        if isinstance(wid, str) and wid and wid in dup_waiver_ids:
            kinds.append("waiver_id")
        ek = w.get("entry_key")
        if isinstance(ek, str) and ek and ek in dup_entry_keys:
            kinds.append("entry_key")
        return kinds

    # =================================================================
    # Phase 1 — Per-row state assignment (precedence order)
    # =================================================================
    for i, w in enumerate(waivers):
        duplicate_kinds = _row_dup_kinds(i)

        # 1. Malformed check
        err = _validate_waiver_row(w, i, now, known_anchors)
        if err is not None:
            ev: _WaiverEval = {
                "waiver_id": w.get("waiver_id", f"<index {i}>"),
                "status": "malformed",
                "error": err,
                "matches": [],
                "waiver_index": i,
                "base_ceiling": w.get("base_ceiling"),
                "ceiling": w.get("ceiling"),
                "decision_ref": w.get("decision_ref"),
            }
            if duplicate_kinds:
                ev["duplicate_kinds"] = duplicate_kinds
            evaluations[i] = ev
            continue

        wid = w["waiver_id"]
        ek = w["entry_key"]

        # 2/3. Duplicate check (ID or entry_key in full inventory)
        if duplicate_kinds:
            evaluations[i] = {
                "waiver_id": wid,
                "status": "duplicate",
                "error": (f"duplicate {'/'.join(duplicate_kinds)} — all copies disqualified"),
                "matches": [],
                "waiver_index": i,
                "base_ceiling": w.get("base_ceiling"),
                "ceiling": w.get("ceiling"),
                "decision_ref": w.get("decision_ref"),
                "duplicate_kinds": duplicate_kinds,
            }
            continue

        # --- Row passed structural checks; determine fine-grained state ---

        # 4. Expired check (UTC date)
        expires = date.fromisoformat(w["expires_on"])
        if expires < now:
            evaluations[i] = {
                "waiver_id": wid,
                "status": "expired",
                "error": f"waiver expired on {w['expires_on']} (current UTC date: {now})",
                "matches": [],
                "waiver_index": i,
                "base_ceiling": w.get("base_ceiling"),
                "ceiling": w.get("ceiling"),
                "decision_ref": w.get("decision_ref"),
            }
            continue

        # 5. Orphan check — no increase detected for this entry_key
        violation_keys = {v["canonical_key"] for v in violations}
        if ek not in violation_keys:
            evaluations[i] = {
                "waiver_id": wid,
                "status": "orphan",
                "warning": f"entry_key {ek!r} has no corresponding increase",
                "matches": [ek],
                "waiver_index": i,
                "base_ceiling": w.get("base_ceiling"),
                "ceiling": w.get("ceiling"),
                "decision_ref": w.get("decision_ref"),
            }
            continue

        # --- Match against the violation ---
        matched_violation = None
        for v in violations:
            if v["canonical_key"] == ek:
                matched_violation = v
                break

        if matched_violation is None:
            evaluations[i] = {
                "waiver_id": wid,
                "status": "orphan",
                "warning": f"entry_key {ek!r} has no corresponding increase",
                "matches": [ek],
                "waiver_index": i,
                "base_ceiling": w.get("base_ceiling"),
                "ceiling": w.get("ceiling"),
                "decision_ref": w.get("decision_ref"),
            }
            continue

        # 6. Stale base
        if matched_violation["old_value"] != w["base_ceiling"]:
            evaluations[i] = {
                "waiver_id": wid,
                "status": "stale_base",
                "error": (
                    f"base_ceiling {w['base_ceiling']} != "
                    f"merge-base value {matched_violation['old_value']} for {ek}"
                ),
                "matches": [ek],
                "waiver_index": i,
                "base_ceiling": w.get("base_ceiling"),
                "ceiling": w.get("ceiling"),
                "decision_ref": w.get("decision_ref"),
            }
            continue

        # 7. Over ceiling
        if matched_violation["new_value"] > w["ceiling"]:
            evaluations[i] = {
                "waiver_id": wid,
                "status": "over_ceiling",
                "error": (
                    f"current value {matched_violation['new_value']} exceeds waiver "
                    f"ceiling {w['ceiling']} for {ek}"
                ),
                "matches": [ek],
                "waiver_index": i,
                "base_ceiling": w.get("base_ceiling"),
                "ceiling": w.get("ceiling"),
                "decision_ref": w.get("decision_ref"),
            }
            continue

        # 8. Active
        evaluations[i] = {
            "waiver_id": wid,
            "status": "active",
            "matches": [ek],
            "waiver_index": i,
            "base_ceiling": w.get("base_ceiling"),
            "ceiling": w.get("ceiling"),
            "decision_ref": w.get("decision_ref"),
        }

    # =================================================================
    # Phase 2 — Assemble unresolved violations
    # =================================================================
    active_entry_keys: set[str] = set()
    for ev in evaluations:
        if ev is not None and ev["status"] == "active":
            for m in ev.get("matches", []):
                active_entry_keys.add(m)

    for v in violations:
        ck = v["canonical_key"]
        if ck in active_entry_keys:
            continue
        unresolved.append(v)

    # =================================================================
    # Phase 3 — Build evaluation output list (every row gets an entry)
    # =================================================================
    canonical_evals: list[_WaiverEval] = []
    for i, ev in enumerate(evaluations):
        if ev is None:
            w = waivers[i]
            canonical_evals.append(
                {
                    "waiver_id": w.get("waiver_id", f"<index {i}>"),
                    "status": "active",
                    "matches": [],
                    "waiver_index": i,
                    "base_ceiling": w.get("base_ceiling"),
                    "ceiling": w.get("ceiling"),
                    "decision_ref": w.get("decision_ref"),
                }
            )
        else:
            canonical_evals.append(ev)

    return unresolved, canonical_evals


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


_CANONICAL_KEYS = frozenset(
    {
        "error_code",
        "section",
        "canonical_key",
        "old_value",
        "new_value",
        "waiver_id",
        "waiver_status",
        "waiver_base_ceiling",
        "waiver_ceiling",
        "waiver_file",
        "decision_ref",
        "waiver_index",
        "duplicate_kinds",
    }
)


def _make_canonical_entry(
    violation: ComparisonResult | None,
    waiver_eval: dict[str, Any] | None,
    waiver_file: str = "",
) -> dict[str, Any]:
    """
    Build one canonical diagnostic record with all 13 required keys.

    The exact canonical key set for every non-schema-error diagnostic record
    is: ``error_code``, ``section``, ``canonical_key``, ``old_value``,
    ``new_value``, ``waiver_id``, ``waiver_status``, ``waiver_base_ceiling``,
    ``waiver_ceiling``, ``waiver_file``, ``decision_ref``, ``waiver_index``,
    ``duplicate_kinds``.  Every key is present on every record; unavailable
    values are ``None`` and ``duplicate_kinds`` is a deterministic list.

    ``violation`` and ``waiver_eval`` are complementary: one may be ``None``
    when the other carries the data.

    Extra legacy keys are intentionally omitted from the canonical record.
    """
    entry: dict[str, Any] = {}

    # --- Violation-origin fields ---
    if violation is not None:
        entry["error_code"] = violation.get("error_code")
        entry["section"] = violation.get("section")
        entry["canonical_key"] = violation.get("canonical_key")
        entry["old_value"] = violation.get("old_value")
        entry["new_value"] = violation.get("new_value")
    else:
        entry["error_code"] = None
        entry["section"] = None
        entry["canonical_key"] = None
        entry["old_value"] = None
        entry["new_value"] = None

    # --- Waiver-origin fields ---
    if waiver_eval is not None:
        entry["waiver_id"] = waiver_eval.get("waiver_id", None)
        entry["waiver_status"] = waiver_eval.get("status", None)
        entry["waiver_base_ceiling"] = waiver_eval.get("base_ceiling", None)
        entry["waiver_ceiling"] = waiver_eval.get("ceiling", None)
        entry["waiver_file"] = waiver_file or waiver_eval.get("waiver_file", None)
        entry["decision_ref"] = waiver_eval.get("decision_ref", None)
        entry["waiver_index"] = waiver_eval.get("waiver_index", None)
        entry["duplicate_kinds"] = waiver_eval.get("duplicate_kinds", [])
    else:
        entry["waiver_id"] = None
        entry["waiver_status"] = None
        entry["waiver_base_ceiling"] = None
        entry["waiver_ceiling"] = None
        entry["waiver_file"] = waiver_file or None
        # Unwaived violations carry required-reference placeholder
        if violation is not None:
            entry["decision_ref"] = "<required: add waiver or revert increase>"
        else:
            entry["decision_ref"] = None
        entry["waiver_index"] = None
        entry["duplicate_kinds"] = []

    return entry


def _format_canonical_diagnostic(v: dict[str, Any]) -> str:
    """
    Format a single violation record as a human-readable diagnostic line.

    Accepts both raw violation dicts (from ``_compare_indexes``) and
    canonical records (from ``_make_canonical_entry``).
    """
    ec = v.get("error_code", "") or ""
    ck = v.get("canonical_key", "") or ""
    ov = v.get("old_value")
    nv = v.get("new_value")
    ov_str = str(ov) if ov is not None else "?"
    nv_str = str(nv) if nv is not None else "?"
    line = f"  {ec:8s}  {ck:70s}  old={ov_str}  new={nv_str}"

    # decision_ref — canonical record has it; raw violation may not
    dr = v.get("decision_ref")
    if dr is not None:
        line += f"  decision_ref={dr}"
    elif "waiver_id" not in v:
        line += "  decision_ref=<required: add waiver or revert increase>"

    # waiver info — canonical record has waiver_id as None/str; raw
    # violation only has it when a waiver was matched
    wid = v.get("waiver_id")
    if wid is not None:
        wc = v.get("waiver_ceiling") or v.get("ceiling")
        wc_str = str(wc) if wc is not None else "?"
        line += f"  waiver={wid} (ceiling={wc_str})"
    elif "waiver_id" in v and v["waiver_id"] is None:
        # Canonical record with null waiver_id (unwaived) — no waiver info
        pass
    return line


def _build_diagnostics(
    violations: list[ComparisonResult],
    waiver_evaluations: list[dict[str, Any]],
    waiver_file: str = "",
) -> list[dict[str, Any]]:
    """
    Build canonical diagnostics list.

    Every entry is a complete canonical record carrying all 13 required keys
    (see ``_make_canonical_entry``).  ``violations`` and ``unresolved`` remain
    as compatibility subsets (same shape, same keys) when stored in the output.

    Uses one constructor for both violation-origin and waiver-origin entries.
    """
    diagnostics: list[dict[str, Any]] = []

    # Build a map of waiver evaluations by canonical_key (matches[0])
    eval_by_key: dict[str, dict[str, Any]] = {}
    for ev in waiver_evaluations:
        matches = ev.get("matches", [])
        if matches:
            eval_by_key[matches[0]] = ev

    # Build a reverse map: which waiver_eval indices are covered by violations
    covered_indices: set[int] = set()

    for v in violations:
        ck = v.get("canonical_key", "")
        matched_ev = eval_by_key.get(ck)
        if matched_ev is not None:
            w_idx = matched_ev.get("waiver_index", -1)
            covered_indices.add(w_idx)
        entry = _make_canonical_entry(v, matched_ev, waiver_file=waiver_file)
        diagnostics.append(entry)

    # Orphan/lifecycle-only waiver entries that have no matching violation
    for i, ev in enumerate(waiver_evaluations):
        if i in covered_indices:
            continue
        # Check if this eval was already matched via matches list
        w_idx = ev.get("waiver_index", i)
        if w_idx in covered_indices:
            continue
        entry = _make_canonical_entry(None, ev, waiver_file=waiver_file)
        diagnostics.append(entry)

    # Sort: violations first (by error_code, canonical_key), then waivers
    def _sort_key(d: dict[str, Any]) -> tuple:
        has_violation = d.get("error_code") is not None
        ec = d.get("error_code") or ""
        ck = d.get("canonical_key") or ""
        wid = d.get("waiver_id") or ""
        return (0 if has_violation else 1, ec, ck, wid)

    diagnostics.sort(key=_sort_key)
    return diagnostics


def _build_output(
    merge_base: str,
    base_ref: str,
    violations: list[ComparisonResult],
    unresolved: list[ComparisonResult],
    waiver_evaluations: list[dict[str, Any]],
    verdict: str,
    warnings: list[str],
    waiver_file: str = "",
) -> dict[str, Any]:
    """Build the complete output dict for the policy JSON file and stdout."""
    # Build canonical diagnostics
    diagnostics = _build_diagnostics(violations, waiver_evaluations, waiver_file=waiver_file)

    # Compatibility subsets: violations and unresolved contain the same
    # complete canonical records as diagnostics, filtered to only those
    # entries that represent actual increases.
    def _is_violation_entry(d: dict[str, Any]) -> bool:
        return d.get("error_code") is not None

    compat_violations = sorted(
        [d for d in diagnostics if _is_violation_entry(d)],
        key=lambda v: (v.get("error_code") or "", v.get("canonical_key") or ""),
    )
    compat_unresolved: list[dict[str, Any]] = []
    for v in compat_violations:
        if v.get("waiver_status") != "active":
            compat_unresolved.append(v)

    return {
        "schema_version": 1,
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "merge_base": merge_base,
        "base_ref": base_ref,
        "verdict": verdict,
        "waiver_file": waiver_file,
        "summary": {
            "total_violations": len(violations),
            "unresolved_violations": len(compat_unresolved),
            "total_waivers": len(waiver_evaluations),
        },
        "violations": compat_violations,
        "unresolved": compat_unresolved,
        "waiver_evaluations": sorted(
            waiver_evaluations,
            key=lambda w: (w.get("waiver_index", 0), w["waiver_id"]),
        ),
        "diagnostics": diagnostics,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SA121 — merge-base baseline monotonicity gate",
    )
    parser.add_argument(
        "--base-ref",
        help="Override the merge-base reference (e.g. v87, main, HEAD~5)",
        default=None,
    )
    return parser.parse_args(argv)


def _write_error_output(
    source: str,
    path: str,
    message: str,
    code: str = "SCHEMA_ERROR",
) -> None:
    """
    Write a deterministic error envelope and print one stable stderr line.

    Produces an atomically written JSON envelope and a single ``ERROR:`` line
    on stderr.  No traceback or tempfile residue.
    """
    print(f"ERROR: {message}", file=sys.stderr)
    _write_output(
        {
            "schema_version": 1,
            "verdict": "error",
            "error": {
                "code": code,
                "source": source,
                "path": path,
                "message": message,
            },
            "diagnostics": [],
        }
    )


def main(argv: list[str] | None = None) -> int:
    """
    Execute the monotonicity check.

    Returns the exit code (0, 1, or 2).  Every unexpected exception is caught,
    written as a deterministic error artifact, and exits 2 without traceback.

    CR-005: On exit 1, stdout emits ONLY canonical JSON records
    (``json.dumps(record, sort_keys=True)``) for each unresolved violation and
    each non-active blocking waiver diagnostic.  No prose headers, merge-base
    info, waiver-evaluation lifecycle prose, or ``_format_canonical_diagnostic``
    output.  On exit 0, stdout is silent.
    """
    try:
        exit_code, output = _main_impl(argv)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc) if str(exc) else f"{type(exc).__name__}"
        _write_error_output(
            source="main",
            path=sys.argv[0] if sys.argv else "check_quality_baseline_monotonicity.py",
            message=msg,
            code="UNEXPECTED_ERROR",
        )
        return 2

    # CR-005: Exit 1 — emit ONLY canonical JSON records, one per line
    if exit_code == 1:
        output_unresolved: list[dict[str, Any]] = output.get("unresolved", [])
        for record in output_unresolved:
            print(json.dumps(record, sort_keys=True))
        # Also emit non-active blocking waiver diagnostics (lifecycle-only entries)
        _blocking_states = frozenset(
            {"malformed", "duplicate", "expired", "stale_base", "over_ceiling", "orphan"}
        )
        for d in output.get("diagnostics", []):
            ws = d.get("waiver_status")
            if ws is not None and ws in _blocking_states:
                # Skip if already printed via unresolved
                ck = d.get("canonical_key") or ""
                if ck and any(ck == r.get("canonical_key", "") for r in output_unresolved):
                    continue
                print(json.dumps(d, sort_keys=True))

    return exit_code


def _main_impl(argv: list[str] | None = None) -> tuple[int, dict[str, Any] | None]:
    """
    Execute the monotonicity check (internal, wrapped by ``main()``).

    CR-005: Returns ``(exit_code, output)``.  Does NOT print anything to stdout.
    ``main()`` handles all stdout emission.  ``_write_output()`` is called here
    on the success path so the canonical policy file is always written.
    """
    args = _parse_args(argv)
    warnings: list[str] = []

    # ---- Resolve merge base ------------------------------------------------
    # Determine the effective base ref for reporting (resolve before use for
    # accurate error paths)
    effective_ref: str | None = args.base_ref
    if not effective_ref:
        effective_ref = os.environ.get("QUALITY_BASELINE_BASE_REF")
    if not effective_ref:
        effective_ref = os.environ.get("GITHUB_BASE_REF")
    if not effective_ref:
        effective_ref = "v87"

    try:
        merge_base = _resolve_merge_base(args.base_ref)
    except RuntimeError as exc:
        _write_error_output(
            source=_SOURCE_GIT,
            path=effective_ref,
            message=f"Merge-base resolution failed: {exc}",
            code="MERGE_BASE_ERROR",
        )
        return 2, None

    # ---- Load current baseline ---------------------------------------------
    baseline_path = os.environ.get("QUALITY_BASELINE_FILE", str(_DEFAULT_BASELINE))
    try:
        current = _load_json(baseline_path)
    except RuntimeError as exc:
        _write_error_output(source=_SOURCE_CURRENT, path=baseline_path, message=str(exc))
        return 2, None

    # ---- Load merge-base baseline from Git ---------------------------------
    try:
        base_blob = _load_json_from_git(merge_base, _CANONICAL_BASELINE_REPO_PATH)
    except RuntimeError as exc:
        msg = str(exc)
        _write_error_output(
            source=_SOURCE_MERGE_BASE,
            path=_CANONICAL_BASELINE_REPO_PATH,
            message=msg,
        )
        return 2, None

    if base_blob is None:
        msg = f"{_CANONICAL_BASELINE_REPO_PATH} does not exist at merge-base {merge_base}"
        _write_error_output(
            source=_SOURCE_MERGE_BASE,
            path=_CANONICAL_BASELINE_REPO_PATH,
            message=msg,
            code="MERGE_BASE_ERROR",
        )
        return 2, None

    # ---- Validate baseline structure (both blobs) + get validated indexes ---
    try:
        base_indexes = _validate_baseline_structure(base_blob, _SOURCE_MERGE_BASE)
        current_indexes = _validate_baseline_structure(current, _SOURCE_CURRENT)
    except SchemaValidationError as exc:
        _write_error_output(source=exc.source, path=exc.path, message=exc.message)
        return 2, None

    # ---- Compare using validated indexes -----------------------------------
    violations: list[ComparisonResult] = _compare_indexes(base_indexes, current_indexes)

    # ---- Load waivers ------------------------------------------------------
    waiver_path = os.environ.get("QUALITY_WAIVERS_FILE", str(_DEFAULT_WAIVERS))
    try:
        waivers = _load_waivers(waiver_path)
    except (RuntimeError, SchemaValidationError) as exc:
        if isinstance(exc, SchemaValidationError):
            _write_error_output(source=exc.source, path=exc.path, message=exc.message)
        else:
            _write_error_output(source=_SOURCE_WAIVER, path=str(waiver_path), message=str(exc))
        return 2, None

    # ---- Pre-compute decision anchors for waiver validation ----------------
    decisions_path = _REPO_ROOT / "docs" / "technical" / "decisions.md"
    known_anchors = _get_decision_anchors(decisions_path)

    # ---- Evaluate waivers (authoritative state machine) --------------------
    # Use UTC date for expiry comparison per the state machine spec
    now_utc = datetime.now(UTC).date()

    unresolved, waiver_evals = _evaluate_violations(
        violations,
        waivers,
        now_utc,
        known_anchors,
        waiver_file=str(waiver_path),
    )

    # ---- Determine verdict -------------------------------------------------
    # Every non-active ledger state blocks; missing coverage blocks.
    _blocking_states = {"malformed", "duplicate", "expired", "stale_base", "over_ceiling", "orphan"}
    has_blocking_waiver = any(ev["status"] in _blocking_states for ev in waiver_evals)

    if not violations and not has_blocking_waiver:
        verdict = "pass"
        exit_code = 0
    elif not unresolved and not has_blocking_waiver:
        verdict = "pass_waived"
        exit_code = 0
    else:
        verdict = "violation"
        exit_code = 1

    # ---- Build canonical output first (CR-005) --------------------------
    output = _build_output(
        merge_base=merge_base,
        base_ref=effective_ref,
        violations=violations,
        unresolved=unresolved,
        waiver_evaluations=waiver_evals,
        verdict=verdict,
        warnings=warnings,
        waiver_file=str(waiver_path),
    )

    # ---- Write output (always on success path) --------------------------
    _write_output(output)

    return exit_code, output


def _write_output(data: dict[str, Any]) -> None:
    """Atomically write the output dict to ``.quickscale/quality_baseline_policy.json``."""
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, indent=2, default=str) + "\n"
    fd, tmp_path = tempfile.mkstemp(
        dir=str(_OUTPUT_DIR),
        prefix=".quality_baseline_policy_tmp.",
        suffix=".json",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp_path, str(_OUTPUT_FILE))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


if __name__ == "__main__":
    sys.exit(main())
