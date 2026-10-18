#!/usr/bin/env python3
"""Exercise fresh-first beta migration compatibility on isolated generated projects."""

# The implementation lives in private ``_beta_migration_smoke_*`` siblings
# (SA267): ``_beta_migration_smoke_support`` (fixture generation, verification
# shims, migration execution, and the shared assertion helpers) and
# ``_beta_migration_smoke_cases`` (the smoke cases).  This module owns the
# entrypoint and re-exports the pre-split surface for unchanged import paths,
# so a test's seam is the sibling that defines the name (decisions.md,
# Split-Facade Seams).

# ruff: noqa: E402 — the sys.path bootstrap must precede the sibling imports.

from __future__ import annotations

import hashlib as hashlib
import json as json
import os as os
import subprocess as subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any as Any

from quickscale_core.generator import ProjectGenerator as ProjectGenerator
from quickscale_core.schema.state_schema import (
    ManagedFileRecord as ManagedFileRecord,
)
from quickscale_core.schema.state_schema import (
    ProjectState as ProjectState,
)
from quickscale_core.schema.state_schema import (
    QuickScaleState as QuickScaleState,
)
from quickscale_core.schema.state_schema import (
    StateManager as StateManager,
)
from quickscale_core.utils.project_identity import (
    resolve_project_identity as resolve_project_identity,
)

# Ensure the private siblings are importable whether this file is executed
# directly (``sys.path[0]`` is ``scripts/``) or imported with only the
# repository root on ``sys.path`` (``scripts.check_beta_migration_smoke``).
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _beta_migration_smoke_cases import (
    _case_fresh_first as _case_fresh_first,
)
from _beta_migration_smoke_cases import (
    _case_gap_handoff as _case_gap_handoff,
)
from _beta_migration_smoke_cases import (
    _case_iterate as _case_iterate,
)
from _beta_migration_smoke_cases import (
    _case_pre_port_surfaces as _case_pre_port_surfaces,
)
from _beta_migration_smoke_cases import (
    _case_project_apps as _case_project_apps,
)
from _beta_migration_smoke_cases import (
    _write_project_app as _write_project_app,
)
from _beta_migration_smoke_support import (
    BETA_MIGRATE as BETA_MIGRATE,
)
from _beta_migration_smoke_support import (
    ROOT as ROOT,
)
from _beta_migration_smoke_support import (
    SHIM_NAMES as SHIM_NAMES,
)
from _beta_migration_smoke_support import (
    SmokeError as SmokeError,
)
from _beta_migration_smoke_support import (
    _assert_common_report as _assert_common_report,
)
from _beta_migration_smoke_support import (
    _assert_non_mutating_run as _assert_non_mutating_run,
)
from _beta_migration_smoke_support import (
    _assert_recipient_services_lifecycle as _assert_recipient_services_lifecycle,
)
from _beta_migration_smoke_support import (
    _assert_successful_execution as _assert_successful_execution,
)
from _beta_migration_smoke_support import (
    _generate_project as _generate_project,
)
from _beta_migration_smoke_support import (
    _install_verification_shims as _install_verification_shims,
)
from _beta_migration_smoke_support import (
    _probe_generated_runtime as _probe_generated_runtime,
)
from _beta_migration_smoke_support import (
    _require as _require,
)
from _beta_migration_smoke_support import (
    _run_migration as _run_migration,
)
from _beta_migration_smoke_support import (
    _snapshot_tree as _snapshot_tree,
)
from _beta_migration_smoke_support import (
    _text_paths_containing as _text_paths_containing,
)
from _beta_migration_smoke_support import (
    _write_quickscale_yml as _write_quickscale_yml,
)

#: Every name the facade re-exports.  Per decisions.md § Split-Facade Seams a
#: facade re-exports public names only: incidental imported bindings
#: (``hashlib``, ``json``, ``Path``, ...) stay module attributes but are
#: deliberately not part of the wildcard surface.
__all__ = [
    "BETA_MIGRATE",
    "ROOT",
    "SHIM_NAMES",
    "SmokeError",
    "main",
]


def main() -> int:
    print("🔍 Beta migration generated-project smoke gate")
    previous_skip_lock = os.environ.get("QS_SKIP_POETRY_LOCK")
    os.environ["QS_SKIP_POETRY_LOCK"] = "1"
    try:
        with tempfile.TemporaryDirectory(prefix="quickscale-beta-migration-smoke-") as temp:
            root = Path(temp)
            spy_log = root / "verification-subprocesses.log"
            shim_dir = _install_verification_shims(root, spy_log)
            environment = dict(os.environ)
            environment["QS_SMOKE_SPY_LOG"] = str(spy_log)
            environment["PATH"] = os.pathsep.join((str(shim_dir), environment["PATH"]))

            print("  🔍 fresh-first compatibility, provenance, skew, and execution")
            _case_fresh_first(root / "fresh-first", environment, spy_log)
            print("    ✅ fresh-first covered non-mutation, fail-closed skew, and execution")
            print("  🔍 iterate regeneration and execution")
            _case_iterate(root / "iterate", environment, spy_log)
            print("    ✅ iterate covered dry-run planning, staged apply, and execution")
            print("  🔍 project-owned app copy, registration, URL mount, and dependency merge")
            _case_project_apps(root / "project-apps", environment, spy_log)
            print("    ✅ project-apps covered app migration and frontend dependency merge")
            print("  🔍 pre-port build surface recording and handoff prompt")
            _case_pre_port_surfaces(root / "pre-port", environment, spy_log)
            print("    ✅ pre-port covered recorded failure, continued stack, and prompt")
            print("  🔍 donor module-divergence gap emission and the handoff file")
            _case_gap_handoff(root / "gap-handoff", environment, spy_log)
            print(
                "    ✅ gap-handoff covered the emitted module-divergence gap in report and prompt"
            )
    finally:
        if previous_skip_lock is None:
            os.environ.pop("QS_SKIP_POETRY_LOCK", None)
        else:
            os.environ["QS_SKIP_POETRY_LOCK"] = previous_skip_lock

    print("✅ Beta migration generated-project smoke gate passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, SmokeError, ValueError, json.JSONDecodeError) as exc:
        print(f"❌ Beta migration smoke gate failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
