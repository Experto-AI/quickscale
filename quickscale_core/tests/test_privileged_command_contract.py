"""Cross-station regressions for the privileged Django command contract."""

from __future__ import annotations

import ast
from pathlib import Path
import re
import subprocess

import pytest
from jinja2 import Environment


ROOT = Path(__file__).parents[2]
EXPECTED_PRIVILEGED_COMMANDS = frozenset({"migrate", "createcachetable"})
DECLARATION_STATIONS = (
    (
        ROOT / "quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py",
        "_PRIVILEGED_COMMANDS",
    ),
    (
        ROOT / "quickscale_cli/src/quickscale_cli/commands/development_commands.py",
        "_PRIVILEGED_DJANGO_COMMANDS",
    ),
    (
        ROOT / "quickscale_core/src/quickscale_core/runtime/settings.py",
        "KNOWN_PRIVILEGED_COMMANDS",
    ),
)


@pytest.mark.parametrize(("path", "symbol"), DECLARATION_STATIONS)
def test_privileged_command_station_names_exact_reduced_set(
    path: Path,
    symbol: str,
) -> None:
    """Every set-bearing station names both members and no retired command."""
    source = path.read_text()
    declaration = re.search(
        rf"{re.escape(symbol)}(?:\s*:\s*[^=]+)?\s*=\s*frozenset\(\s*(\{{.*?\}})\s*\)",
        source,
        re.DOTALL,
    )

    assert declaration is not None, f"missing {symbol} declaration in {path}"
    observed = frozenset(ast.literal_eval(declaration.group(1)))
    assert observed == EXPECTED_PRIVILEGED_COMMANDS


def test_start_sh_names_exact_reduced_set() -> None:
    """The launcher emits privileged prefixes for exactly the sanctioned set."""
    template = (
        ROOT / "quickscale_core/src/quickscale_core/generator/templates/start.sh.j2"
    ).read_text()

    observed = frozenset(
        re.findall(r"QUICKSCALE_PRIVILEGED_COMMAND=([a-z_]+)", template)
    )

    assert observed == EXPECTED_PRIVILEGED_COMMANDS


def test_start_sh_rejects_supplied_argv(tmp_path: Path) -> None:
    """A supplied argv exits 2 before any privileged path can run."""
    template = (
        ROOT / "quickscale_core/src/quickscale_core/generator/templates/start.sh.j2"
    ).read_text()
    rendered = Environment().from_string(template).render(package_name="testproject")
    launcher = tmp_path / "start.sh"
    launcher.write_text(rendered)

    result = subprocess.run(
        ["bash", str(launcher), "some_unsupported_command"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == (
        "ERROR: unsupported start.sh command: some_unsupported_command\n"
    )
