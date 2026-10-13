#!/usr/bin/env python3
"""
Run QuickScale's fail-closed dependency and static-security gates.

The wrapper intentionally owns scanner acquisition and adjudication.  Callers
must not need to know how Trivy is downloaded, which files are scanned, or how
the accountable suppression ledger is interpreted.
"""

# The docstring above is user-visible: ``main`` prints ``__doc__`` as the
# ``--help`` description, so it stays byte-identical to the pre-split module
# and the split architecture is documented here instead.
#
# The implementation lives in private ``_security_gates_*`` siblings (SA267):
# ``_security_gates_support`` (gate errors, the fail-closed command runner, the
# strict JSON decoder, and the process/temporary-directory cleanup),
# ``_security_gates_trivy`` (checksum-pinned Trivy acquisition, the lockfile
# vulnerability scan, and the generated-Dockerfile misconfiguration scan),
# ``_security_gates_bandit`` (source discovery and the Bandit static scan),
# ``_security_gates_adjudication`` (suppression-ledger loading and finding
# adjudication), and ``_security_gates_probes`` (the negative-probe controls).
# This module owns the CLI dispatch and re-exports the pre-split surface for
# unchanged import paths, so a test's seam is the sibling that defines the name
# (decisions.md, Split-Facade Seams).

# ruff: noqa: E402 — the sys.path bootstrap must precede the sibling imports.

from __future__ import annotations

import argparse as argparse
import atexit as atexit
import hashlib as hashlib
import json as json
import os as os
import platform as platform
import re as re
import shutil as shutil
import signal as signal
import stat as stat
import subprocess as subprocess
import sys
import tarfile as tarfile
import tempfile as tempfile
from dataclasses import dataclass as dataclass
from datetime import date as date
from pathlib import Path
from typing import Any as Any
from urllib.parse import urlparse as urlparse
from urllib.request import Request as Request
from urllib.request import urlopen as urlopen

# Ensure the private siblings are importable whether this file is executed
# directly (``sys.path[0]`` is ``scripts/``) or imported with only the
# repository root on ``sys.path`` (``scripts.check_security_gates``).
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import _security_gates_bandit as _bandit
import _security_gates_probes as _probes
import _security_gates_trivy as _trivy
from _security_gates_adjudication import (
    SUPPRESSION_KEYS,
    SUPPRESSIONS_PATH,
    _adjudicate,
    _load_suppressions,
)
from _security_gates_bandit import (
    BANDIT_TESTS,
    BANDIT_VERSION,
    CATEGORY_TESTS,
    EXCLUDED_PARTS,
    MODULES_ROOT,
    _bandit_findings,
    _bandit_fingerprint,
    _bandit_project,
    _bandit_scan,
    _discover_module_source_roots,
    _source_files,
    _source_roots,
    static_gate,
)
from _security_gates_probes import (
    BAD_DOCKERFILE_PROBE,
    PROBES_PATH,
    _probe_lock,
    negative_probes,
)
from _security_gates_support import (
    COMMAND_TIMEOUT,
    ROOT,
    Completed,
    FindingsError,
    GateError,
    _cleanup,
    _new_temp_dir,
    _signal_handler,
    _terminate_process_group,
    run_command,
    strict_json,
)
from _security_gates_trivy import (
    GENERATED_PROJECT_SLUG,
    LOCK_NAME,
    MISCONFIG_SEVERITIES,
    TRIVY_ASSETS,
    TRIVY_RELEASE_URL,
    TRIVY_VERSION,
    _download,
    _generated_dockerfile,
    _load_toml,
    _lock_inventory,
    _misconfig_command,
    _run_dependency_gate,
    _safe_archive_members,
    _trivy_asset,
    _trivy_finding,
    _trivy_misconfig_scan,
    _trivy_scan,
    acquire_trivy,
    dependency_gate,
)

#: Every name the facade re-exports.  Per decisions.md § Split-Facade Seams a
#: facade re-exports public names only: incidental imported bindings
#: (``argparse``, ``Path``, ``platform``, ...) stay module attributes but are
#: deliberately not part of the wildcard surface.
__all__ = [
    "BAD_DOCKERFILE_PROBE",
    "BANDIT_TESTS",
    "BANDIT_VERSION",
    "CATEGORY_TESTS",
    "COMMAND_TIMEOUT",
    "Completed",
    "EXCLUDED_PARTS",
    "FindingsError",
    "GENERATED_PROJECT_SLUG",
    "GateError",
    "LOCK_NAME",
    "MISCONFIG_SEVERITIES",
    "MODULES_ROOT",
    "PROBES_PATH",
    "ROOT",
    "SUPPRESSIONS_PATH",
    "SUPPRESSION_KEYS",
    "TRIVY_ASSETS",
    "TRIVY_RELEASE_URL",
    "TRIVY_VERSION",
    "_adjudicate",
    "_bandit_findings",
    "_bandit_fingerprint",
    "_bandit_project",
    "_bandit_scan",
    "_cleanup",
    "_discover_module_source_roots",
    "_download",
    "_generated_dockerfile",
    "_load_suppressions",
    "_load_toml",
    "_lock_inventory",
    "_misconfig_command",
    "_new_temp_dir",
    "_probe_lock",
    "_run_dependency_gate",
    "_safe_archive_members",
    "_signal_handler",
    "_source_files",
    "_source_roots",
    "_terminate_process_group",
    "_trivy_asset",
    "_trivy_finding",
    "_trivy_misconfig_scan",
    "_trivy_scan",
    "acquire_trivy",
    "dependency_gate",
    "main",
    "negative_probes",
    "run_command",
    "static_gate",
    "strict_json",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        nargs="?",
        choices=(
            "dependency",
            "dependency-vulnerabilities",
            "static",
            "static-analysis",
            "security-static-analysis",
            "negative-probes",
            "security-negative-probes",
        ),
    )
    parser.add_argument(
        "--mode",
        dest="mode_option",
        choices=(
            "dependency",
            "dependency-vulnerabilities",
            "static",
            "static-analysis",
            "security-static-analysis",
            "negative-probes",
            "security-negative-probes",
        ),
    )
    args = parser.parse_args(argv)
    if args.mode and args.mode_option and args.mode != args.mode_option:
        parser.error("positional mode and --mode must agree")
    mode = args.mode_option or args.mode
    if mode in {"dependency", "dependency-vulnerabilities"}:
        return _trivy.dependency_gate()
    if mode in {"static", "static-analysis", "security-static-analysis"}:
        return _bandit.static_gate()
    if mode in {"negative-probes", "security-negative-probes"}:
        return _probes.negative_probes()
    parser.error("a scanner mode is required")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FindingsError as exc:
        print(f"security findings: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except GateError as exc:
        print(f"security gate infrastructure failure: {exc}", file=sys.stderr)
        raise SystemExit(2)
