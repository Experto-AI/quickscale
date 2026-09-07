#!/usr/bin/env python3
"""
Failure replay for local iteration.

`make ci` and the E2E runner buffer or interleave their output, so after a long
run the failing tests are somewhere in a wall of text and the command that
re-runs just those has to be reconstructed by hand.  This helper removes that
step.

No new dependency is involved: pytest already records failing node ids in
`.pytest_cache/v/cache/lastfailed` under each rootdir.  ``record`` snapshots
those caches together with the CI stage that failed and writes a consolidated
`.quickscale/last-failures.json`; ``replay`` turns that file back into the exact
``make`` commands (``make retry`` runs them).

Known limitation: stages that run pytest with ``-p no:cacheprovider``
(``check-gate-suites``, ``test-postgres-provisioning``) write no cache, so those
produce a stage-level repro command rather than individual node ids.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORD_PATH = REPO_ROOT / ".quickscale" / "last-failures.json"

STAGE_FALLBACK = {
    "install": "make ci ONLY=install",
    "static": "make ci ONLY=static",
    "coverage": "make ci ONLY=coverage",
    "integration": "make ci ONLY=integration",
    "e2e": "make test-e2e",
    "unit": "make test-unit",
}


def _roots() -> list[tuple[str, Path]]:
    """Every pytest rootdir that keeps its own cache, as (kind, path)."""
    roots: list[tuple[str, Path]] = [
        ("core", REPO_ROOT / "quickscale_core"),
        ("cli", REPO_ROOT / "quickscale_cli"),
    ]
    modules_dir = REPO_ROOT / "quickscale_modules"
    if modules_dir.is_dir():
        for module in sorted(modules_dir.iterdir()):
            if (module / "tests").is_dir():
                roots.append(("module", module))
    return roots


def _read_lastfailed(root: Path, since: float | None = None) -> list[str]:
    cache = root / ".pytest_cache" / "v" / "cache" / "lastfailed"
    if not cache.is_file():
        return []
    if since is not None:
        # pytest keeps lastfailed until a run clears it, so a cache untouched by
        # the run we are recording holds failures from some earlier, unrelated
        # session. Replaying those would be actively misleading, so anything
        # older than the stage start is ignored.
        try:
            if cache.stat().st_mtime < since:
                return []
        except OSError:
            return []
    try:
        data = json.loads(cache.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return []
    if not isinstance(data, dict):
        return []
    # Keys are node ids relative to the rootdir; values are truthy for failures.
    return sorted(str(key) for key, value in data.items() if value)


def _test_names(node_ids: list[str]) -> list[str]:
    """
    Reduce node ids to bare test-function names for a ``-k`` expression.

    ``-k`` is used rather than raw node ids because the make targets already
    pass a test *directory* as pytest's positional argument; appending a node id
    would add a second selection instead of narrowing the first.  Parametrised
    ids are trimmed to the function name, and a name that also exists in another
    file may pull in that sibling too -- an over-selection that still runs in
    seconds, which is the point.
    """
    names: list[str] = []
    for node_id in node_ids:
        name = node_id.rsplit("::", 1)[-1]
        name = name.split("[", 1)[0].strip()
        if name and name not in names:
            names.append(name)
    return names


def _repro(stage: str, kind: str, root: Path, names: list[str]) -> str:
    """
    Build the make command that re-runs one rootdir's failures.

    The target is chosen from the rootdir kind rather than from the stage:
    `make test-integration` only runs module suites, so a core or CLI failure
    must map to `test-unit` (or `test-e2e`) whatever stage surfaced it.
    """
    if kind == "module":
        parts = ["make", "test-integration", f"MODULE={root.name}"]
    elif stage == "e2e":
        parts = ["make", "test-e2e"]
    else:
        parts = ["make", "test-unit", f"SECTIONS={kind}"]
    keyword = " or ".join(names)
    if keyword:
        parts.append(f"K={shlex.quote(keyword)}")
    return " ".join(parts)


def _collect(stage: str, since: float | None = None) -> dict:
    entries = []
    for kind, root in _roots():
        node_ids = _read_lastfailed(root, since)
        if not node_ids:
            continue
        names = _test_names(node_ids)
        entries.append(
            {
                "kind": kind,
                "root": str(root.relative_to(REPO_ROOT)),
                "module": root.name if kind == "module" else None,
                "ids": node_ids,
                "repro": _repro(stage, kind, root, names),
            }
        )
    return {
        "stage": stage,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "entries": entries,
        "fallback_repro": STAGE_FALLBACK.get(stage, "make ci"),
    }


def _cmd_record(args: argparse.Namespace) -> int:
    record = _collect(args.stage, args.since)
    RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECORD_PATH.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    count = sum(len(entry["ids"]) for entry in record["entries"])
    if count:
        print(f"Recorded {count} failing test(s) — re-run them with: make retry")
    else:
        # No cache means the stage failed outside pytest, or ran with
        # -p no:cacheprovider. The stage-level command is still worth having.
        print("No fresh pytest failure cache found — re-run the stage with: make retry")
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    if not RECORD_PATH.is_file():
        # Deliberately not falling back to a live cache scan: pytest keeps
        # lastfailed until a run clears it, so an unbounded scan would happily
        # replay failures from days ago as if they were current.
        message = (
            "No recorded failures. Run `make ci` (or a make test target) first; "
            "the failing stage writes .quickscale/last-failures.json."
        )
        if args.quiet:
            return 0
        print(message)
        return 0

    try:
        record = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR: unreadable {RECORD_PATH}: {exc}", file=sys.stderr)
        return 2

    commands = [entry["repro"] for entry in record.get("entries", []) if entry.get("repro")]
    if not commands:
        fallback = record.get("fallback_repro") or "make ci"
        if args.quiet:
            print(fallback)
        else:
            print("No individual failing tests were recorded.")
            print(f"Nearest re-run: {fallback}")
        return 0

    if args.quiet:
        for command in commands:
            print(command)
        return 0

    print(
        f"Last failing stage: {record.get('stage', 'unknown')}"
        f" (recorded {record.get('recorded_at', 'unknown')})"
    )
    for entry in record.get("entries", []):
        print(f"  {entry['root']}: {len(entry['ids'])} failing")
    print("")
    for command in commands:
        print(command)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="snapshot pytest failure caches")
    record.add_argument("--stage", default="unit", help="CI stage that failed")
    record.add_argument(
        "--since",
        type=float,
        default=None,
        help="ignore failure caches not modified at or after this epoch time",
    )
    record.set_defaults(func=_cmd_record)

    replay = sub.add_parser("replay", help="print the commands that re-run the failures")
    replay.add_argument(
        "--quiet",
        action="store_true",
        help="print only the commands, one per line (used by `make retry`)",
    )
    replay.set_defaults(func=_cmd_replay)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
