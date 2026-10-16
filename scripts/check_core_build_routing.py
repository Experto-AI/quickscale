"""
Reject quickscale_core wheel builds outside the one shared core-build step.

SA285 (b): every entrypoint that builds the ``quickscale_core`` wheel routes
through ``scripts/build_core_wheel.sh`` (directly or through ``make
build-core``), which materializes the bundled module manifests first.  This
checker scans the executable build surfaces — every shell script under
``scripts/`` and ``.github/``, every Python script under ``scripts/`` (its
``subprocess``/``os.system`` build calls), the root ``Makefile``, and the
``run`` blocks of workflow and composite-action YAML under ``.github/`` — and
reports every ``poetry build`` command the shared step does not own.

Scan contract:

- ``scripts/build_core_wheel.sh`` owns the core build and is exempt.
- Every other ``poetry build`` command must declare that it builds a non-core
  package with the exact trailing comment ``# non-core wheel build``.
- A declared command whose build directory is statically resolvable to the
  core package is still a violation: a literal ``quickscale_core`` path in the
  command, or a ``cd``/``--directory`` (shell) or ``cwd=`` (Python) target that
  is a variable assigned a ``quickscale_core`` path elsewhere in the same file.

Known limit: a build directory computed at runtime from a loop or positional
variable cannot be resolved statically, so a declared command of that shape is
accepted; the declaration is the reviewable claim, and the detectable core
bindings above still fail closed.  Generated ``scripts/gates.mk`` is out of
scope.
"""

from __future__ import annotations

import argparse
import ast
import re
from collections.abc import Iterator
from pathlib import Path

import yaml

SHARED_STEP_RELATIVE = Path("scripts") / "build_core_wheel.sh"
NON_CORE_DECLARATION = "# non-core wheel build"

_SUBPROCESS_METHODS = {"call", "check_call", "check_output", "run", "Popen"}
_OS_SHELL_METHODS = {"system", "popen"}
_RESOLUTION_DEPTH = 4

_BUILD_COMMAND = re.compile(r"\bpoetry\s+build\b")
_CORE_TOKEN = re.compile(r"(?<![\w.-])quickscale_core(?![\w-])")
_BUILD_DIRECTORY = re.compile(
    r"(?:\bcd\b|--directory)[ \t]+(?P<target>\"[^\"]*\"|'[^']*'|[^\s;&|]+)"
)
_VARIABLE_REFERENCE = re.compile(r"\$\{?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}?")
_DECLARATION = re.compile(r"#\s*non-core wheel build\s*$")
_ASSIGNMENT = re.compile(
    r"^[ \t]*(?:(?:export|local|readonly)[ \t]+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>.*)$"
)


def _strip_quotes(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def _assigned_values(lines: list[str]) -> dict[str, list[str]]:
    """Collect simple same-file assignments for the variable-resolution rule."""
    values: dict[str, list[str]] = {}
    for line in lines:
        if line.lstrip().startswith("#"):
            continue
        match = _ASSIGNMENT.match(line)
        if match is None:
            continue
        values.setdefault(match.group("name"), []).append(match.group("value"))
    return values


def _core_binding(line: str, values: dict[str, list[str]]) -> tuple[str, str] | None:
    """Return a reason and the offending reference when the build directory is core."""
    literal = _CORE_TOKEN.search(line)
    if literal is not None:
        return "resolves to the core package", literal.group(0)
    for match in _BUILD_DIRECTORY.finditer(line):
        target = _strip_quotes(match.group("target"))
        if _CORE_TOKEN.search(target):
            return "runs in a core build directory", target
        for reference in _VARIABLE_REFERENCE.finditer(target):
            assigned = values.get(reference.group("name"), [])
            if any(_CORE_TOKEN.search(value) for value in assigned):
                return "runs in a variable-bound core build directory", reference.group(0)
    return None


def _scan_lines(label: str, lines: list[str]) -> list[str]:
    values = _assigned_values(lines)
    violations: list[str] = []
    for number, line in enumerate(lines, 1):
        if line.lstrip().startswith("#") or _BUILD_COMMAND.search(line) is None:
            continue
        binding = _core_binding(line, values)
        if binding is not None:
            reason, reference = binding
            violations.append(
                f"{label}:{number}: `poetry build` {reason} outside "
                f"{SHARED_STEP_RELATIVE}: {reference}"
            )
        elif _DECLARATION.search(line) is None:
            violations.append(
                f"{label}:{number}: `poetry build` outside {SHARED_STEP_RELATIVE} "
                f"must carry `{NON_CORE_DECLARATION}`"
            )
    return violations


def _string_fragments(node: ast.AST, assignments: dict[str, ast.AST], depth: int = 0) -> list[str]:
    """Collect constant string fragments from an argument or an assigned value."""
    if depth > _RESOLUTION_DEPTH:
        return []
    if isinstance(node, ast.Name):
        assigned = assignments.get(node.id)
        if assigned is None:
            return []
        return _string_fragments(assigned, assignments, depth + 1)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple)):
        fragments: list[str] = []
        for element in node.elts:
            fragments.extend(_string_fragments(element, assignments, depth))
        return fragments
    if isinstance(node, ast.JoinedStr):
        fragments = []
        for value in node.values:
            fragments.extend(_string_fragments(value, assignments, depth))
        return fragments
    return []


def _is_build_executor(call: ast.Call) -> bool:
    function = call.func
    if not isinstance(function, ast.Attribute) or not isinstance(function.value, ast.Name):
        return False
    if function.value.id == "subprocess":
        return function.attr in _SUBPROCESS_METHODS
    if function.value.id == "os":
        return function.attr in _OS_SHELL_METHODS
    return False


def _declared_within(lines: list[str], call: ast.Call) -> bool:
    end = getattr(call, "end_lineno", None) or call.lineno
    for number in range(call.lineno, end + 1):
        if number <= len(lines) and _DECLARATION.search(lines[number - 1]):
            return True
    return False


def _python_violations(path: Path, source: str) -> list[str]:
    """Report subprocess/os build calls whose command is not the shared step's."""
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [f"{path}: unreadable Python source: {exc}"]
    assignments: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assignments[node.target.id] = node.value
    lines = source.splitlines()
    violations: list[str] = []
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if not _is_build_executor(call):
            continue
        fragments: list[str] = []
        for argument in call.args:
            fragments.extend(_string_fragments(argument, assignments))
        for keyword in call.keywords:
            if keyword.arg in {"args", "cwd"}:
                fragments.extend(_string_fragments(keyword.value, assignments))
        text = " ".join(fragments)
        if _BUILD_COMMAND.search(text) is None:
            continue
        literal = _CORE_TOKEN.search(text)
        if literal is not None:
            violations.append(
                f"{path}:{call.lineno}: `poetry build` resolves to the core package "
                f"outside {SHARED_STEP_RELATIVE}: {literal.group(0)}"
            )
        elif not _declared_within(lines, call):
            violations.append(
                f"{path}:{call.lineno}: `poetry build` outside {SHARED_STEP_RELATIVE} "
                f"must carry `{NON_CORE_DECLARATION}`"
            )
    return violations


def _iter_run_blocks(document: object) -> Iterator[str]:
    if not isinstance(document, dict):
        return
    jobs = document.get("jobs")
    if not isinstance(jobs, dict):
        return
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps")
        if not isinstance(steps, list):
            continue
        for step in steps:
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                yield step["run"]


def _iter_action_run_blocks(document: object) -> Iterator[str]:
    if not isinstance(document, dict):
        return
    runs = document.get("runs")
    if not isinstance(runs, dict):
        return
    steps = runs.get("steps")
    if not isinstance(steps, list):
        return
    for step in steps:
        if isinstance(step, dict) and isinstance(step.get("run"), str):
            yield step["run"]


def _yaml_violations(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [f"{path}: unreadable YAML: {exc}"]
    violations: list[str] = []
    for run_block in (*_iter_run_blocks(document), *_iter_action_run_blocks(document)):
        violations.extend(_scan_lines(f"{path} run block", run_block.splitlines()))
    return violations


def _scan_shell_files(directory: Path, shared_step: Path) -> list[str]:
    violations: list[str] = []
    for shell_file in sorted(directory.rglob("*.sh")):
        if shell_file.resolve() == shared_step:
            continue
        violations.extend(
            _scan_lines(
                str(shell_file),
                shell_file.read_text(encoding="utf-8").splitlines(),
            )
        )
    return violations


def find_violations(root: Path) -> list[str]:
    """Return one line per ``poetry build`` command the shared step does not own."""
    violations: list[str] = []
    shared_step = (root / SHARED_STEP_RELATIVE).resolve()
    scripts_dir = root / "scripts"
    if scripts_dir.is_dir():
        violations.extend(_scan_shell_files(scripts_dir, shared_step))
        for python_file in sorted(scripts_dir.rglob("*.py")):
            violations.extend(
                _python_violations(
                    python_file,
                    python_file.read_text(encoding="utf-8"),
                )
            )
    makefile = root / "Makefile"
    if makefile.is_file():
        violations.extend(
            _scan_lines(str(makefile), makefile.read_text(encoding="utf-8").splitlines())
        )
    github_dir = root / ".github"
    if github_dir.is_dir():
        violations.extend(_scan_shell_files(github_dir, shared_step))
        yaml_files = sorted([*github_dir.rglob("*.yml"), *github_dir.rglob("*.yaml")])
        for yaml_file in yaml_files:
            violations.extend(_yaml_violations(yaml_file))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    violations = find_violations(args.root.resolve())
    if violations:
        for violation in violations:
            print(f"ERROR: {violation}")
        return 1
    print("Core build routing check passed: only the shared step builds quickscale_core.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
