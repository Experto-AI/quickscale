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
        ROOT / "quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py",
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


def test_launchers_name_exact_reduced_set() -> None:
    """The privileged prefix set lives only in the pre-deploy launcher."""
    predeploy = (
        ROOT / "quickscale_core/src/quickscale_core/generator/templates/predeploy.sh.j2"
    ).read_text()
    start_sh = (
        ROOT / "quickscale_core/src/quickscale_core/generator/templates/start.sh.j2"
    ).read_text()

    observed = frozenset(
        re.findall(r"QUICKSCALE_PRIVILEGED_COMMAND=([a-z_]+)", predeploy)
    )

    assert observed == EXPECTED_PRIVILEGED_COMMANDS
    assert "QUICKSCALE_PRIVILEGED_COMMAND" not in start_sh


@pytest.mark.parametrize("launcher_name", ["start.sh", "predeploy.sh"])
def test_launchers_reject_supplied_argv(launcher_name: str, tmp_path: Path) -> None:
    """A supplied argv exits 2 before any privileged path can run."""
    template = (
        ROOT
        / f"quickscale_core/src/quickscale_core/generator/templates/{launcher_name}.j2"
    ).read_text()
    rendered = Environment().from_string(template).render(package_name="testproject")
    launcher = tmp_path / launcher_name
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
        f"ERROR: unsupported {launcher_name} command: some_unsupported_command\n"
    )
