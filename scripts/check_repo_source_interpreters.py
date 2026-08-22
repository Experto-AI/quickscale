"""Reject bare interpreters when repository Python sources are executed."""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

_BARE_SHELL_EXECUTOR = re.compile(
    r"(?<![A-Za-z0-9_./-])python(?:3)?[ \t]+"
    r"(?:(?:-[A-Za-z][^ \t\n]*|--[^ \t\n]+)[ \t]+)*"
    r"(?P<target>[\"'][^\"']+\.py[\"']|[^ \t\n#]+\.py)"
)
_SHELL_ASSIGNMENT = re.compile(
    r"^[ \t]*(?:export[ \t]+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>.*)$"
)
_BARE_PYTHON_DEFAULT = re.compile(
    r"(?:^[\"']?python(?:3)?[\"']?$|\$\{[A-Za-z_][A-Za-z0-9_]*:-python(?:3)?\})"
)
_SUBPROCESS_METHODS = {"call", "check_call", "check_output", "run", "Popen"}
_BARE_PYTHON_NAMES = {"python", "python3"}


def _shell_assignment_sets(lines: list[str]) -> tuple[set[str], set[str]]:
    bare_python_variables: set[str] = set()
    python_source_variables: set[str] = set()
    for line in lines:
        if line.lstrip().startswith("#"):
            continue
        match = _SHELL_ASSIGNMENT.match(line)
        if match is None:
            continue
        name = match.group("name")
        value = match.group("value").split("#", 1)[0].strip()
        if _BARE_PYTHON_DEFAULT.search(value):
            bare_python_variables.add(name)
        if re.search(r"\.py(?:[\"']|[ \t]|$)", value):
            python_source_variables.add(name)
    return bare_python_variables, python_source_variables


def _indirect_shell_violations(path: Path, lines: list[str]) -> list[str]:
    bare_python_variables, python_source_variables = _shell_assignment_sets(lines)
    violations: list[str] = []
    for line_number, line in enumerate(lines, 1):
        if line.lstrip().startswith("#"):
            continue
        for variable in bare_python_variables:
            executor = re.search(
                rf'(?<![A-Za-z0-9_./-])(?:"\${variable}"|\$\{{{variable}\}}|\${variable})(?=[ \t])',
                line,
            )
            if executor is None:
                continue
            arguments = line[executor.end() :]
            literal_source = re.search(r"\.py(?:[\"']|[ \t]|$)", arguments)
            variable_source = any(
                re.search(
                    rf'(?:"\${source_variable}"|\$\{{{source_variable}\}}|\${source_variable})',
                    arguments,
                )
                for source_variable in python_source_variables
            )
            if literal_source is not None or variable_source:
                violations.append(
                    f"{path}:{line_number}: bare Python variable executes a repository .py file"
                )
                break
    return violations


def _shell_violations(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    violations: list[str] = []
    for line_number, line in enumerate(lines, 1):
        if line.lstrip().startswith("#"):
            continue
        for match in _BARE_SHELL_EXECUTOR.finditer(line):
            if line[: match.start()].rstrip().endswith("poetry run"):
                continue
            violations.append(f"{path}:{line_number}: bare Python executes a repository .py file")
    violations.extend(_indirect_shell_violations(path, lines))
    return violations


def _static_sequence(node: ast.AST, assignments: dict[str, ast.AST]) -> list[ast.AST] | None:
    if isinstance(node, ast.Name):
        node = assignments.get(node.id, node)
    if isinstance(node, (ast.List, ast.Tuple)):
        return list(node.elts)
    return None


def _literal_text(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _python_test_violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assignments = {
        target.id: statement.value
        for statement in ast.walk(tree)
        if isinstance(statement, ast.Assign)
        for target in statement.targets
        if isinstance(target, ast.Name)
    }
    violations: list[str] = []
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        function = call.func
        if not isinstance(function, ast.Attribute) or function.attr not in _SUBPROCESS_METHODS:
            continue
        if not isinstance(function.value, ast.Name) or function.value.id != "subprocess":
            continue
        if not call.args:
            continue
        command = _static_sequence(call.args[0], assignments)
        if not command:
            continue
        first = _literal_text(command[0])
        if first not in _BARE_PYTHON_NAMES:
            continue
        if len(command) > 1 and _literal_text(command[1]) == "-c":
            continue
        violations.append(
            f"{path}:{call.lineno}: bare {first} may execute a repository Python source"
        )
    return violations


def find_violations(root: Path) -> list[str]:
    violations: list[str] = []
    for shell_file in sorted((root / "scripts").glob("*.sh")):
        violations.extend(_shell_violations(shell_file))
    for test_file in sorted((root / "scripts").glob("test_*.py")):
        violations.extend(_python_test_violations(test_file))
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
    print("Repository-source interpreter check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
