"""Regression tests for billing package imports."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_top_level_billing_imports_do_not_trigger_circular_dependency() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    module_src = repository_root / "quickscale_modules" / "billing" / "src"
    script = """
from importlib import import_module
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd() / "quickscale_modules" / "billing" / "src"))
import quickscale_modules_billing
from quickscale_modules_billing.apps import QuickscaleBillingConfig

assert quickscale_modules_billing.__version__
config = QuickscaleBillingConfig(
    \"quickscale_modules_billing\",
    import_module(\"quickscale_modules_billing\"),
)
config.ready()
"""

    pythonpath = os.pathsep.join(
        [
            str(module_src),
            os.environ.get("PYTHONPATH", ""),
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        check=False,
        cwd=repository_root,
        env={**os.environ, "PYTHONPATH": pythonpath},
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
