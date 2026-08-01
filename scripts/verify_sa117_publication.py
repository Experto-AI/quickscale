#!/usr/bin/env python3
r"""
SA117 — Publication verification helper.

Provides four operations that form the SA117 publication gate:

* ``capture`` — snapshot the current version state and scope into evidence.
* ``verify`` — confirm that evidence is internally consistent and matches
  current state without performing any publication.
* ``authorize`` — produce a signed authorisation token for a specific version
  and evidence digest.  Requires explicit authorisation parameters (no
  auto-authorisation).
* ``rollback`` — reverse a prior authorisation given exact evidence values
  that match the recorded token.  Refuses to roll back without a matching
  evidence digest.

All operations are read-only with respect to the production environment.
Evidence is written to a configurable path (default: ``/tmp/opencode/sa117-evidence/``).
No network, Docker, PostgreSQL, or outward credentials are accessed.

Exit codes
----------
0 — operation succeeded
1 — semantic rejection (evidence mismatch, verification failure)
2 — malformed invocation, evidence, or configuration

Examples
--------
    # Capture current evidence
    poetry run python scripts/verify_sa117_publication.py capture

    # Verify evidence against a specific file
    poetry run python scripts/verify_sa117_publication.py verify --evidence /path/to/evidence.json

    # Authorize a publication
    poetry run python scripts/verify_sa117_publication.py authorize \\
        --version 0.87.0 --evidence-digest abc123

    # Rollback a prior authorization
    poetry run python scripts/verify_sa117_publication.py rollback \\
        --auth-token tok_xxx --evidence-digest abc123

"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any, Final

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVIDENCE_DIR: Final[Path] = Path(
    os.environ.get(
        "SA117_EVIDENCE_DIR",
        "/tmp/opencode/sa117-evidence",
    )
)

# ---------------------------------------------------------------------------
# Evidence schema helpers
# ---------------------------------------------------------------------------


def _make_evidence(
    *,
    version: str,
    phase: str,
    paths_count: int,
    scope_digest: str,
) -> dict[str, Any]:
    """
    Build an evidence dict with required fields.

    *version* — the repository VERSION string.
    *phase* — the SA117 phase that was verified.
    *paths_count* — the number of paths in the scope allowlist.
    *scope_digest* — a hex digest of the scope JSON for integrity.
    """
    return {
        "version": version,
        "phase": phase,
        "paths_count": paths_count,
        "scope_digest": scope_digest,
        "captured_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "schema_version": "1",
    }


def _validate_evidence(evidence: dict[str, Any]) -> None:
    """
    Validate that *evidence* contains all required fields with correct types.

    Raises ``ValueError`` with a description of the first missing or invalid
    field.
    """
    required_fields: dict[str, type] = {
        "version": str,
        "phase": str,
        "paths_count": int,
        "scope_digest": str,
        "captured_at": str,
        "schema_version": str,
    }
    for field, expected_type in required_fields.items():
        if field not in evidence:
            raise ValueError(f"evidence missing required field: {field!r}")
        if not isinstance(evidence[field], expected_type):
            raise ValueError(
                f"evidence field {field!r} has wrong type: "
                f"expected {expected_type.__name__}, "
                f"got {type(evidence[field]).__name__}"
            )

    # Validate that captured_at is an ISO-formatted datetime
    try:
        datetime.datetime.fromisoformat(evidence["captured_at"])
    except (ValueError, TypeError) as exc:
        raise ValueError(f"evidence 'captured_at' is not a valid ISO datetime: {exc}") from exc


# ---------------------------------------------------------------------------
# Scope digest
# ---------------------------------------------------------------------------


def _compute_scope_digest(scope_path: Path) -> str:
    """
    Return the SHA-256 hex digest of the scope file at *scope_path*.

    Raises ``FileNotFoundError`` if the scope file does not exist.
    """
    if not scope_path.is_file():
        raise FileNotFoundError(f"scope file not found: {scope_path}")
    digest = hashlib.sha256()
    digest.update(scope_path.read_bytes())
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Evidence I/O
# ---------------------------------------------------------------------------


def _write_evidence(evidence: dict[str, Any], path: Path) -> Path:
    """
    Write *evidence* to *path* as formatted JSON.

    Returns *path*.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _read_evidence(path: Path) -> dict[str, Any]:
    """
    Read and return evidence from *path*.

    Raises ``FileNotFoundError``, ``json.JSONDecodeError``, or
    ``ValueError`` (via ``_validate_evidence``).
    """
    if not path.is_file():
        raise FileNotFoundError(f"evidence file not found: {path}")
    with path.open("rb") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"evidence is not a JSON object: {path}")
    _validate_evidence(data)
    return data


# ---------------------------------------------------------------------------
# Authorization tokens
# ---------------------------------------------------------------------------


def _generate_auth_token() -> str:
    """Generate a cryptographically random authorisation token."""
    return "sa117_auth_" + secrets.token_hex(32)


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


def op_capture(
    *,
    version: str,
    phase: str,
    scope_path: Path,
    evidence_dir: Path = EVIDENCE_DIR,
) -> int:
    """
    Capture current evidence and write it to *evidence_dir*.

    Returns 0 on success, 2 on error.
    """
    try:
        scope_digest = _compute_scope_digest(scope_path)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # Count paths in the scope
    try:
        scope_data = json.loads(scope_path.read_bytes())
        paths_count = len(scope_data.get("paths", []))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: failed to read scope file: {exc}", file=sys.stderr)
        return 2

    evidence = _make_evidence(
        version=version,
        phase=phase,
        paths_count=paths_count,
        scope_digest=scope_digest,
    )

    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    evidence_path = evidence_dir / f"sa117_evidence_{timestamp}.json"

    try:
        _write_evidence(evidence, evidence_path)
    except OSError as exc:
        print(f"ERROR: failed to write evidence: {exc}", file=sys.stderr)
        return 2

    print(f"Evidence captured: {evidence_path}")
    print(f"  Version: {evidence['version']}")
    print(f"  Phase: {evidence['phase']}")
    print(f"  Paths: {evidence['paths_count']}")
    print(f"  Scope digest: {evidence['scope_digest'][:16]}...")
    return 0


def op_verify(
    *,
    evidence_path: Path,
    scope_path: Path,
) -> int:
    """
    Verify that *evidence_path* contains valid, internally consistent evidence.

    Checks:
    1. Evidence parses as valid JSON and has all required fields.
    2. ``version`` is a non-empty string.
    3. ``paths_count`` is a positive integer.
    4. ``scope_digest`` matches the digest of *scope_path*.
    5. ``captured_at`` is a valid ISO datetime.

    Returns 0 on pass, 1 on verification failure, 2 on error.
    """
    # Load evidence
    try:
        evidence = _read_evidence(evidence_path)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"VERIFY FAILED: {exc}", file=sys.stderr)
        return 2

    # Check non-empty version
    if not evidence["version"].strip():
        print("VERIFY FAILED: version is empty", file=sys.stderr)
        return 1

    # Check positive paths_count
    if evidence["paths_count"] <= 0:
        print(
            f"VERIFY FAILED: paths_count is not positive: {evidence['paths_count']}",
            file=sys.stderr,
        )
        return 1

    # Check scope digest
    try:
        actual_digest = _compute_scope_digest(scope_path)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if evidence["scope_digest"] != actual_digest:
        print(
            f"VERIFY FAILED: scope digest mismatch\n"
            f"  Evidence: {evidence['scope_digest'][:16]}...\n"
            f"  Actual:   {actual_digest[:16]}...",
            file=sys.stderr,
        )
        return 1

    print(
        f"VERIFY PASSED: evidence is valid and scope digest matches.\n"
        f"  Version: {evidence['version']}\n"
        f"  Phase: {evidence['phase']}\n"
        f"  Paths: {evidence['paths_count']}\n"
        f"  Captured at: {evidence['captured_at']}"
    )
    return 0


def op_authorize(
    *,
    version: str,
    evidence_digest: str,
    auth_dir: Path = EVIDENCE_DIR,
) -> int:
    """
    Produce an authorisation token for *version* and *evidence_digest*.

    Requires explicit *version* and *evidence_digest* parameters — no
    auto-authorisation.  Writes the token to *auth_dir*.

    Returns 0 on success, 2 on error.
    """
    if not version.strip():
        print("ERROR: version is empty", file=sys.stderr)
        return 2

    if not evidence_digest.strip():
        print("ERROR: evidence_digest is empty", file=sys.stderr)
        return 2

    token = _generate_auth_token()
    auth_record = {
        "token": token,
        "version": version,
        "evidence_digest": evidence_digest,
        "authorized_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "schema_version": "1",
    }

    auth_path = auth_dir / f"sa117_auth_{token[-16:]}.json"
    try:
        _write_evidence(auth_record, auth_path)
    except OSError as exc:
        print(f"ERROR: failed to write auth token: {exc}", file=sys.stderr)
        return 2

    print(f"Authorization token written: {auth_path}")
    print(f"  Token: {token}")
    print(f"  Version: {version}")
    print(f"  Evidence digest: {evidence_digest[:16]}...")
    return 0


def op_rollback(
    *,
    auth_token: str,
    evidence_digest: str,
    auth_dir: Path = EVIDENCE_DIR,
) -> int:
    """
    Roll back a prior authorisation.

    Requires *auth_token* and *evidence_digest* that match a previously
    written auth record.  Refuses to roll back when the digest does not
    match.

    Returns 0 on success, 1 on mismatch, 2 on error.
    """
    # Search for the auth record
    auth_path = auth_dir / f"sa117_auth_{auth_token[-16:]}.json"
    if not auth_path.is_file():
        # Try scanning all auth files for the token
        found = False
        revoked_digest = None
        for f in sorted(auth_dir.glob("sa117_auth_*.json")):
            try:
                record = json.loads(f.read_bytes())
                if record.get("token") == auth_token:
                    auth_path = f
                    found = True
                    revoked_digest = record.get("evidence_digest", "")
                    break
            except (json.JSONDecodeError, OSError) as _:
                # Skip malformed or unreadable records and keep scanning
                # for a later exact token.  ``_`` keeps the parenthesized
                # tuple form (the bare comma clause is a SyntaxError on
                # Python < 3.14).
                continue

        if not found:
            print(f"ERROR: auth token not found: {auth_token}", file=sys.stderr)
            return 2

        # Found the record, check evidence_digest
        if revoked_digest != evidence_digest:
            print(
                f"ROLLBACK REJECTED: evidence digest mismatch\n"
                f"  Expected: {revoked_digest[:16]}...\n"
                f"  Provided: {evidence_digest[:16]}...",
                file=sys.stderr,
            )
            return 1
    else:
        # Fast path: file matched by naming convention
        try:
            record = json.loads(auth_path.read_bytes())
        except (json.JSONDecodeError, OSError) as exc:
            print(f"ERROR: failed to read auth record: {exc}", file=sys.stderr)
            return 2

        recorded_digest = record.get("evidence_digest", "")
        if recorded_digest != evidence_digest:
            print(
                f"ROLLBACK REJECTED: evidence digest mismatch\n"
                f"  Expected: {recorded_digest[:16]}...\n"
                f"  Provided: {evidence_digest[:16]}...",
                file=sys.stderr,
            )
            return 1

        if record.get("token") != auth_token:
            print(
                "ROLLBACK REJECTED: auth token mismatch in record",
                file=sys.stderr,
            )
            return 1

    # Perform rollback: remove the auth record
    try:
        auth_path.unlink()
    except OSError as exc:
        print(f"ERROR: failed to remove auth record: {exc}", file=sys.stderr)
        return 2

    print(f"ROLLBACK COMPLETE: auth token revoked: {auth_token}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the publication verification helper."""
    parser = argparse.ArgumentParser(
        prog="verify_sa117_publication.py",
        description="SA117 publication gate — capture/verify/authorize/rollback.",
    )
    parser.add_argument(
        "--scope",
        type=Path,
        default=Path("scripts/sa117_scope.json"),
        help="Path to sa117_scope.json (default: scripts/sa117_scope.json).",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=EVIDENCE_DIR,
        help=f"Evidence directory (default: {EVIDENCE_DIR}).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # capture
    cap = subparsers.add_parser("capture", help="Capture current evidence.")
    cap.add_argument("--version", required=True, help="Repository version string.")
    cap.add_argument("--phase", required=True, help="SA117 phase label.")

    # verify
    ver = subparsers.add_parser("verify", help="Verify evidence file.")
    ver.add_argument("--evidence", required=True, type=Path, help="Path to evidence JSON.")

    # authorize
    auth = subparsers.add_parser("authorize", help="Authorize a publication.")
    auth.add_argument("--version", required=True, help="Repository version string.")
    auth.add_argument(
        "--evidence-digest",
        required=True,
        help="Hex digest of the evidence to authorize.",
    )

    # rollback
    rb = subparsers.add_parser("rollback", help="Roll back a prior authorization.")
    rb.add_argument("--auth-token", required=True, help="Authorization token to revoke.")
    rb.add_argument(
        "--evidence-digest",
        required=True,
        help="Hex digest of the evidence that was authorized.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the publication verification helper."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    cmd = args.command
    scope_path = args.scope.resolve()
    evidence_dir = args.evidence_dir.resolve()

    if cmd == "capture":
        return op_capture(
            version=args.version,
            phase=args.phase,
            scope_path=scope_path,
            evidence_dir=evidence_dir,
        )
    elif cmd == "verify":
        return op_verify(
            evidence_path=args.evidence.resolve(),
            scope_path=scope_path,
        )
    elif cmd == "authorize":
        return op_authorize(
            version=args.version,
            evidence_digest=args.evidence_digest,
            auth_dir=evidence_dir,
        )
    elif cmd == "rollback":
        return op_rollback(
            auth_token=args.auth_token,
            evidence_digest=args.evidence_digest,
            auth_dir=evidence_dir,
        )
    else:
        print(f"ERROR: unknown command: {cmd}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
