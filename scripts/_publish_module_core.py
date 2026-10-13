"""
Shared base surface for the ``publish_module`` facade and its private siblings.

This module owns the repository root anchor, the operator output helpers, the
authoritative module inventory, and the repository version checks.  Every
private sibling resolves those collaborators here at call time, so a test's
seam is the module that defines the name (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

import sys
from pathlib import Path

from quickscale_core.utils.git_utils import GitError

# The repository root anchor.  ``publish_module.py`` and every private sibling
# live in ``scripts/``; the facade keeps the public ``_REPO_ROOT`` attribute
# through its re-export block.
_REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Output helpers (match the bash script's color conventions)
# ---------------------------------------------------------------------------

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
NC = "\033[0m"


def _print_info(msg: str) -> None:
    print(f"{BLUE}ℹ️  {msg}{NC}")


def _print_success(msg: str) -> None:
    print(f"{GREEN}✅ {msg}{NC}")


def _print_warning(msg: str) -> None:
    print(f"{YELLOW}⚠️  {msg}{NC}")


def _print_error(msg: str) -> None:
    print(f"{RED}❌ {msg}{NC}")


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _list_modules() -> list[str]:
    """Return the fail-hard authoritative shipped-module inventory."""
    from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
        authoritative_module_names,
    )

    return authoritative_module_names()


def _require_authoritative_module(module_name: str) -> None:
    """
    Fail closed unless *module_name* is in the authoritative shipped-module inventory.

    This is the direct single-module selector guard (F-002): it consults
    :func:`_list_modules` (backed by ``authoritative_module_names()``)
    before any release-authority check, origin prompt, subtree split, or
    push.  An unapproved inventory addition (count drift) therefore fails
    before any outward or mutating path, instead of relying on on-disk
    directory existence alone.
    """
    from quickscale_core.contracts.module_discovery import (  # noqa: PLC0415
        ImproperlyConfigured,
    )

    try:
        authoritative_names = _list_modules()
    except ImproperlyConfigured as exc:
        _print_error(f"Authoritative module inventory unavailable: {exc}")
        sys.exit(1)

    if module_name not in authoritative_names:
        _print_error(
            f"Module '{module_name}' is not in the authoritative shipped-module inventory."
        )
        print()
        _print_info("Available modules:")
        for name in authoritative_names:
            print(f"  - {name}")
        sys.exit(1)


def _read_repository_version() -> str:
    """Read the repository VERSION value used by implicit status."""
    try:
        version = (_REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise GitError(f"Could not read repository VERSION: {exc}") from exc
    if not version:
        raise GitError("Repository VERSION is empty")
    return version


def _validate_seal_version(requested_version: str) -> None:
    """Bind a requested seal version to the repository's authoritative value."""
    try:
        repository_version = _read_repository_version()
    except GitError as exc:
        _print_error(str(exc))
        sys.exit(1)
    if requested_version == repository_version:
        return
    _print_error(
        "Seal version mismatch: "
        f"requested {requested_version}, repository VERSION {repository_version}"
    )
    sys.exit(1)
