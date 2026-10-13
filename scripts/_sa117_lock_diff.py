"""
Lock normalisation, structural diffing, and evidence writing for the SA267(d) split.

Only the twelve approved module ``package.version`` leaves are normalised; the
rest of the lock structure is compared exactly and the deterministic evidence
document is written through an atomic same-directory replace.  The facade
imports these names from this defining sibling, never through the facade
(decisions.md, Split-Facade Seams).  Behavior is unchanged from the pre-split
module.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from _sa117_lock_parse import _LOCK_VERSION_SENTINEL, LockDiffError


def _normalise_lock(
    lock_data: dict[str, Any], module_packages: list[str]
) -> tuple[dict[str, Any], list[str]]:
    """Deep-copy a lock and replace only validated module version leaves."""
    normalised = copy.deepcopy(lock_data)
    leaves: list[str] = []
    for package in normalised["package"]:
        if package["name"] in module_packages:
            package["version"] = _LOCK_VERSION_SENTINEL
            leaves.append(f"package[{package['name']}].version")
    if sorted(leaves) != sorted(f"package[{name}].version" for name in module_packages):
        raise LockDiffError("lock normalisation did not find every validated module leaf")
    return normalised, sorted(leaves)


def _collect_differences(left: Any, right: Any, path: str = "") -> list[dict[str, Any]]:
    """Collect deterministic structural differences for evidence."""
    if type(left) is not type(right):
        return [{"path": path or "$", "baseline": left, "candidate": right}]
    if isinstance(left, dict):
        differences: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right), key=str):
            child = f"{path}.{key}" if path else str(key)
            if key not in left or key not in right:
                differences.append(
                    {"path": child, "baseline": left.get(key), "candidate": right.get(key)}
                )
            else:
                differences.extend(_collect_differences(left[key], right[key], child))
        return differences
    if isinstance(left, list):
        differences = []
        for index in range(max(len(left), len(right))):
            child = f"{path}[{index}]"
            if index >= len(left) or index >= len(right):
                differences.append(
                    {
                        "path": child,
                        "baseline": left[index] if index < len(left) else None,
                        "candidate": right[index] if index < len(right) else None,
                    }
                )
            else:
                differences.extend(_collect_differences(left[index], right[index], child))
        return differences
    if left != right:
        return [{"path": path or "$", "baseline": left, "candidate": right}]
    return []


def _remove_evidence(path: Path) -> None:
    """Remove stale evidence after output-path safety checks pass."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise LockDiffError(f"cannot remove stale evidence {path}: {exc}") from exc


def _write_evidence_atomic(path: Path, evidence: dict[str, Any]) -> None:
    """Write deterministic JSON through an atomic same-directory replace."""
    fd: int | None = None
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary_path = Path(temporary)
        encoded = (
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except Exception as exc:
        cleanup_errors: list[OSError] = []
        if fd is not None:
            try:
                os.close(fd)
            except OSError as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                cleanup_errors.append(cleanup_error)
        if cleanup_errors:
            raise LockDiffError(
                f"cannot clean temporary evidence for {path}: {cleanup_errors[0]}"
            ) from exc
        raise LockDiffError(f"cannot write evidence {path}: {exc}") from exc
