"""
Focused tests for ``scripts/check_core_build_routing.py`` (SA285 (b)).

The checker proves that every ``quickscale_core`` wheel build in the shell
build surfaces routes through the one shared core-build step.  These tests
assert the real repository is clean and exercise the positive and negative
controls: an undeclared core build, a declared build that is still statically
core, a Makefile build, and a workflow run block.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from check_core_build_routing import NON_CORE_DECLARATION, find_violations

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = Path(__file__).resolve().parent / "check_core_build_routing.py"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_real_repository_routes_every_core_build_through_the_shared_step() -> None:
    assert find_violations(REPO_ROOT) == []


def test_clean_tree_passes_with_controls_available(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "other.sh", "echo no builds here\n")
    assert find_violations(tmp_path) == []
    result = _run_checker(tmp_path)
    assert result.returncode == 0
    assert "passed" in result.stdout


def test_undeclared_core_build_in_shell_script_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "bad.sh", "cd quickscale_core && poetry build\n")

    violations = find_violations(tmp_path)

    assert len(violations) == 1
    assert "bad.sh" in violations[0]
    assert "quickscale_core" in violations[0]
    result = _run_checker(tmp_path)
    assert result.returncode == 1
    assert "bad.sh" in result.stdout


def test_undeclared_non_core_build_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "scripts" / "bad.sh", "(cd quickscale_cli && poetry build)\n")

    violations = find_violations(tmp_path)

    assert len(violations) == 1
    assert NON_CORE_DECLARATION in violations[0]


def test_declared_non_core_build_is_allowed(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts" / "ok.sh",
        'pkg_dir=other\n(cd "$pkg_dir" && poetry build)  # non-core wheel build\n',
    )

    assert find_violations(tmp_path) == []


def test_declaration_cannot_launder_a_literal_core_binding(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts" / "bad.sh",
        "cd quickscale_core && poetry build  # non-core wheel build\n",
    )

    violations = find_violations(tmp_path)

    assert len(violations) == 1
    assert "core" in violations[0]


def test_variable_bound_core_directory_is_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts" / "bad.sh",
        'CORE_DIR="$ROOT/quickscale_core"\n'
        '(cd "$CORE_DIR" && poetry build)  # non-core wheel build\n',
    )

    violations = find_violations(tmp_path)

    assert len(violations) == 1
    assert "variable-bound core" in violations[0]


def test_makefile_core_build_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "Makefile", "build:\n\tcd quickscale_core && poetry build\n")

    violations = find_violations(tmp_path)

    assert len(violations) == 1
    assert "Makefile" in violations[0]
    assert "quickscale_core" in violations[0]


def test_workflow_core_build_is_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "bad.yml",
        "name: bad\n"
        "on: push\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: Build\n"
        "        run: |\n"
        "          (cd quickscale_core && poetry build)\n",
    )

    violations = find_violations(tmp_path)

    assert len(violations) == 1
    assert "bad.yml" in violations[0]
    assert "quickscale_core" in violations[0]


def test_shared_step_owns_the_core_build(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts" / "build_core_wheel.sh",
        'package_dir="$ROOT/quickscale_core"\n(cd "$package_dir" && poetry build)\n',
    )

    assert find_violations(tmp_path) == []


def test_python_script_core_build_is_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts" / "bad.py",
        "import subprocess\n"
        'subprocess.run("cd quickscale_core && poetry build", shell=True, check=True)\n',
    )

    violations = find_violations(tmp_path)

    assert len(violations) == 1
    assert "bad.py" in violations[0]
    assert "quickscale_core" in violations[0]


def test_python_script_docstring_mention_is_allowed(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts" / "ok.py",
        '"""Materializes the manifests before ``poetry build`` for quickscale_core."""\n',
    )

    assert find_violations(tmp_path) == []


def test_python_script_declared_non_core_build_is_allowed(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts" / "ok.py",
        "import subprocess\n"
        'subprocess.run(["poetry", "build"], cwd="quickscale_cli")'
        "  # non-core wheel build\n",
    )

    assert find_violations(tmp_path) == []


def test_python_script_variable_bound_core_directory_is_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts" / "bad.py",
        "import subprocess\n"
        'core_dir = "quickscale_core"\n'
        'subprocess.run(["poetry", "build"], cwd=core_dir)\n',
    )

    violations = find_violations(tmp_path)

    assert len(violations) == 1
    assert "quickscale_core" in violations[0]


def test_python_script_keyword_command_core_build_is_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts" / "bad.py",
        'import subprocess\nsubprocess.run(args=["poetry", "build"], cwd="quickscale_core")\n',
    )

    violations = find_violations(tmp_path)

    assert len(violations) == 1
    assert "quickscale_core" in violations[0]


def test_composite_action_core_build_is_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path / ".github" / "actions" / "build" / "action.yml",
        "name: build\n"
        "runs:\n"
        "  using: composite\n"
        "  steps:\n"
        "    - name: Build\n"
        "      shell: bash\n"
        "      run: |\n"
        "        (cd quickscale_core && poetry build)\n",
    )

    violations = find_violations(tmp_path)

    assert len(violations) == 1
    assert "action.yml" in violations[0]
    assert "quickscale_core" in violations[0]
