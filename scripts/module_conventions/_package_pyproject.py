"""
Rule 18's one pyproject template and every module's diff against it.

Every module's ``pyproject.toml`` carries the tables and the shared values
below in this order, so the stale "centralized in root" comment, orgs' ``>=``
dev floors, and the one-off ``pythonpath`` variants cannot return.
Implementation detail of :mod:`scripts.module_conventions.rules_package`; that
module re-exports every moved name so existing import paths keep working.
"""

from __future__ import annotations

import re
import shlex
import tomllib
from collections.abc import Mapping

from scripts.module_conventions.core import MODULE_IMPORT_PREFIX, Module

# Rule 18's one pyproject template (SA293 (c)).  Every module's
# ``pyproject.toml`` carries these tables in this order, and every shared value
# below is diffed literally, so the stale "centralized in root" comment, orgs'
# ``>=`` dev floors, and the one-off ``pythonpath`` variants cannot return.
# The per-module slots are the project name and description, the package
# include, the module's own runtime and dev dependency names, and its extras.
PYPROJECT_TEMPLATE_TABLES = (
    "project",
    "tool.poetry",
    "tool.poetry.dependencies",
    "tool.poetry.extras",
    "tool.poetry.group.dev.dependencies",
    "build-system",
    "tool.ruff",
    "tool.ruff.lint",
    "tool.ruff.lint.per-file-ignores",
    "tool.pytest.ini_options",
    "tool.coverage.report",
    "tool.django-stubs",
)

#: The one table a module may omit: the optional-dependency group.
PYPROJECT_OPTIONAL_TABLES = ("tool.poetry.extras",)

#: The stale authorship claim the template forbids in the raw file text.
PYPROJECT_TEMPLATE_STALE_COMMENT = "centralized in root"

#: ``[project]`` keys the template leaves to the module; ``version`` is the
#: release version ``make version-check`` keeps equal across the tree.
PYPROJECT_PROJECT_PER_MODULE_KEYS = ("name", "version", "description")

PYPROJECT_TEMPLATE_PROJECT: dict[str, object] = {
    "requires-python": ">=3.14,<3.15",
    "readme": "README.md",
    "license": "Apache-2.0",
    "authors": [{"name": "Experto AI", "email": "victor@experto.ai"}],
    "dynamic": ["dependencies"],
}

PYPROJECT_TEMPLATE_RUNTIME: dict[str, object] = {
    "python": ">=3.14,<3.15",
    "Django": ">=6.0.7,<6.1.0",
}

PYPROJECT_TEMPLATE_CORE_DEPENDENCY: dict[str, object] = {
    "path": "../../quickscale_core",
    "develop": True,
}

#: Dev-group specs take the caret form; module-specific names are allowed.
PYPROJECT_TEMPLATE_DEV_DEPENDENCIES: dict[str, object] = {"pytest-django": "^4.11.1"}

#: Tables whose literal content is fixed; each also rejects unknown keys.
PYPROJECT_TEMPLATE_TABLE_VALUES: tuple[tuple[str, dict[str, object]], ...] = (
    (
        "build-system",
        {"requires": ["poetry-core>=2.0,<3.0"], "build-backend": "poetry.core.masonry.api"},
    ),
    ("tool.ruff", {"target-version": "py314"}),
    ("tool.ruff.lint", {"select": ["E4", "E7", "E9", "F", "S"]}),
    ("tool.ruff.lint.per-file-ignores", {"tests/**": ["S"]}),
    ("tool.coverage.report", {"fail_under": 90}),
    ("tool.django-stubs", {"django_settings_module": "tests.settings"}),
)

PYPROJECT_TEMPLATE_PYTEST: dict[str, object] = {
    "DJANGO_SETTINGS_MODULE": "tests.settings",
    "pythonpath": [".", "src", "../.."],
    "python_files": ["test_*.py"],
    "testpaths": ["tests"],
}

#: The marker block every module declares: the union of the markers the 12
#: suites use, so a module that adds one of these behaviours needs no pyproject
#: edit and no suite can use a marker it never declared.
PYPROJECT_TEMPLATE_MARKERS = (
    "bypass_rls: test requires BYPASSRLS database privilege (superuser / migration DDL). "
    "Deselected unless QUICKSCALE_ALLOW_BYPASSRLS is exactly 1.",
    "e2e: End-to-end integration tests that exercise the full user workflow",
    "isolation: cross-tenant isolation tests (roadmap Finding 14 / F11 rollout)",
)


def _coverage_targets(addopts: str) -> list[str | None]:
    """
    Return every ``--cov`` target in one addopts string.

    Both spellings pytest-cov accepts are read.  A bare ``--cov`` — at the end
    of the string or followed by another option — yields ``None``: pytest-cov
    treats ``--cov --cov=<name>`` as ``--cov`` alone, dropping the named source
    and measuring everything (``_prepare_cov_source`` returns ``None``).
    """
    try:
        tokens = shlex.split(addopts)
    except ValueError:
        return []
    targets: list[str | None] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--cov":
            value = tokens[index + 1] if index + 1 < len(tokens) else None
            if value is None or value.startswith("-"):
                targets.append(None)
                index += 1
            else:
                targets.append(value)
                index += 2
            continue
        if token.startswith("--cov="):
            targets.append(token[len("--cov=") :])
        index += 1
    return targets


def _coverage_target_violations(module_name: str, ini_options: Mapping[str, object]) -> list[str]:
    """
    Rule 18: ``--cov`` names the module's import package.

    Coherence proposal 18's rule: ``--cov`` names the package
    (``quickscale_modules_<name>``), never a ``src/`` path, so a module's own
    test run measures the package under the name it is imported by.  A
    targetless ``--cov``, which pytest-cov treats as unrestricted, is refused
    with the same weight as a wrong one.
    """
    addopts = ini_options.get("addopts")
    targets = _coverage_targets(addopts) if isinstance(addopts, str) else []
    expected = f"{MODULE_IMPORT_PREFIX}{module_name}"
    if not targets:
        return [f"rule 18: {module_name}: pyproject addopts declares no --cov target"]
    findings: list[str] = []
    for target in targets:
        if target == expected:
            continue
        if target is None:
            findings.append(
                f"rule 18: {module_name}: pyproject --cov takes no target; "
                f"name the import package {expected!r}"
            )
        else:
            findings.append(
                f"rule 18: {module_name}: pyproject --cov target {target!r} does not name "
                f"the import package {expected!r}"
            )
    return findings


def _pyproject_table(data: Mapping[str, object], path: str) -> Mapping[str, object] | None:
    """Return one dotted pyproject table, or None when it is not a table."""
    node: object = data
    for part in path.split("."):
        if not isinstance(node, Mapping):
            return None
        node = node.get(part)
    return node if isinstance(node, Mapping) else None


def _pyproject_table_order(text: str) -> list[str]:
    """Return the pyproject's table headers in document order."""
    return re.findall(r"^\[([^\[\]]+)\]\s*$", text, re.MULTILINE)


def _template_value_violations(
    module_name: str, path: str, table: Mapping[str, object], expected: Mapping[str, object]
) -> list[str]:
    """Rule 18: every shared value in one table equals the template's."""
    findings: list[str] = []
    for key, expected_value in expected.items():
        if key not in table:
            findings.append(f"rule 18: {module_name}: pyproject [{path}] has no {key!r}")
        elif table[key] != expected_value:
            findings.append(
                f"rule 18: {module_name}: pyproject [{path}] {key} is {table[key]!r}; "
                f"the template's is {expected_value!r}"
            )
    return findings


def _template_key_violations(
    module_name: str, path: str, table: Mapping[str, object], allowed: tuple[str, ...]
) -> list[str]:
    """Rule 18: a template table carries no key the template does not declare."""
    return [
        f"rule 18: {module_name}: pyproject [{path}] key {key!r} is not part of the template"
        for key in table
        if key not in allowed
    ]


def _template_child_keys(path: str) -> tuple[str, ...]:
    """Return the template's direct child table names for one dotted table path."""
    prefix = f"{path}."
    return tuple(
        table[len(prefix) :]
        for table in PYPROJECT_TEMPLATE_TABLES
        if table.startswith(prefix) and "." not in table[len(prefix) :]
    )


def _template_structure_violations(module_name: str, text: str) -> list[str]:
    """Rule 18: the stale comment, the tables, and their document order."""
    findings: list[str] = []
    if PYPROJECT_TEMPLATE_STALE_COMMENT in text:
        findings.append(
            f"rule 18: {module_name}: pyproject keeps the stale "
            f"'{PYPROJECT_TEMPLATE_STALE_COMMENT}' comment"
        )
    tables = _pyproject_table_order(text)
    findings.extend(
        f"rule 18: {module_name}: pyproject is missing the [{table}] table"
        for table in PYPROJECT_TEMPLATE_TABLES
        if table not in PYPROJECT_OPTIONAL_TABLES and table not in tables
    )
    findings.extend(
        f"rule 18: {module_name}: pyproject table [{table}] is not part of the template"
        for table in tables
        if table not in PYPROJECT_TEMPLATE_TABLES
    )
    known = [table for table in tables if table in PYPROJECT_TEMPLATE_TABLES]
    expected = [table for table in PYPROJECT_TEMPLATE_TABLES if table in known]
    if known != expected:
        findings.append(f"rule 18: {module_name}: pyproject tables are not in the template order")
    return findings


def _template_project_violations(module: Module, project: Mapping[str, object]) -> list[str]:
    """Rule 18: the [project] table's slots and shared values."""
    expected_name = f"quickscale-module-{module.name}"
    findings: list[str] = []
    if project.get("name") != expected_name:
        findings.append(
            f"rule 18: {module.name}: pyproject name is {project.get('name')!r}; "
            f"the template derives {expected_name!r}"
        )
    if not isinstance(project.get("description"), str) or not project.get("description"):
        findings.append(f"rule 18: {module.name}: pyproject description is missing")
    findings.extend(
        _template_value_violations(module.name, "project", project, PYPROJECT_TEMPLATE_PROJECT)
    )
    findings.extend(
        _template_key_violations(
            module.name,
            "project",
            project,
            (*PYPROJECT_PROJECT_PER_MODULE_KEYS, *PYPROJECT_TEMPLATE_PROJECT),
        )
    )
    return findings


def _template_poetry_violations(module: Module, poetry: Mapping[str, object]) -> list[str]:
    """Rule 18: the [tool.poetry] table's include, keys, and groups."""
    include = f"{MODULE_IMPORT_PREFIX}{module.name}"
    packages = poetry.get("packages")
    findings: list[str] = []
    if packages != [{"include": include, "from": "src"}]:
        findings.append(
            f"rule 18: {module.name}: pyproject [tool.poetry] packages is {packages!r}; "
            f"the template's is a single 'src' include of {include!r}"
        )
    findings.extend(
        _template_key_violations(
            module.name, "tool.poetry", poetry, ("packages", "dependencies", "extras", "group")
        )
    )
    group = _pyproject_table(poetry, "group")
    if group is not None:
        findings.extend(_template_key_violations(module.name, "tool.poetry.group", group, ("dev",)))
        dev_group = _pyproject_table(poetry, "group.dev")
        if dev_group is not None:
            findings.extend(
                _template_key_violations(
                    module.name, "tool.poetry.group.dev", dev_group, ("dependencies",)
                )
            )
    return findings


def _template_runtime_violations(module: Module, runtime: Mapping[str, object]) -> list[str]:
    """Rule 18: the shared runtime pins and the lockstep core dependency."""
    findings = _template_value_violations(
        module.name, "tool.poetry.dependencies", runtime, PYPROJECT_TEMPLATE_RUNTIME
    )
    core = runtime.get("quickscale-core")
    if core != PYPROJECT_TEMPLATE_CORE_DEPENDENCY:
        findings.append(
            f"rule 18: {module.name}: pyproject [tool.poetry.dependencies] quickscale-core is "
            f"{core!r}; the template's is {PYPROJECT_TEMPLATE_CORE_DEPENDENCY!r}"
        )
    return findings


def _template_dev_violations(module: Module, dev: Mapping[str, object]) -> list[str]:
    """Rule 18: the shared dev dependency, and caret specs for the rest."""
    path = "tool.poetry.group.dev.dependencies"
    findings = _template_value_violations(
        module.name, path, dev, PYPROJECT_TEMPLATE_DEV_DEPENDENCIES
    )
    findings.extend(
        f"rule 18: {module.name}: pyproject [{path}] dev dependency {key!r} is {value!r}; "
        "dev specs take the caret form"
        for key, value in dev.items()
        if key not in PYPROJECT_TEMPLATE_DEV_DEPENDENCIES
        and not (isinstance(value, str) and value.startswith("^"))
    )
    return findings


def _template_extras_violations(module: Module, extras: Mapping[str, object]) -> list[str]:
    """Rule 18: each optional-dependency group names its dependencies."""
    return [
        f"rule 18: {module.name}: pyproject [tool.poetry.extras] extra {key!r} is not a "
        "list of dependency names"
        for key, value in extras.items()
        if not (isinstance(value, list) and all(isinstance(item, str) for item in value))
    ]


def _template_pytest_violations(module: Module, table: Mapping[str, object]) -> list[str]:
    """Rule 18: one pytest table — shared values, one marker block, one --cov."""
    path = "tool.pytest.ini_options"
    findings = _template_value_violations(module.name, path, table, PYPROJECT_TEMPLATE_PYTEST)
    markers = table.get("markers")
    if markers != list(PYPROJECT_TEMPLATE_MARKERS):
        findings.append(
            f"rule 18: {module.name}: pyproject [{path}] markers are {markers!r}; "
            f"the template's are {list(PYPROJECT_TEMPLATE_MARKERS)!r}"
        )
    findings.extend(
        _template_key_violations(
            module.name, path, table, (*PYPROJECT_TEMPLATE_PYTEST, "addopts", "markers")
        )
    )
    findings.extend(_coverage_target_violations(module.name, table))
    return findings


def _pyproject_template_violations(
    module: Module, data: Mapping[str, object], text: str
) -> list[str]:
    """Rule 18: one module's pyproject diffed against the shared template."""
    findings = _template_structure_violations(module.name, text)
    findings.extend(
        f"rule 18: {module.name}: pyproject key {key!r} is not part of the template"
        for key in data
        if key not in ("project", "tool", "build-system")
    )
    project = _pyproject_table(data, "project")
    if project is not None:
        findings.extend(_template_project_violations(module, project))
    poetry = _pyproject_table(data, "tool.poetry")
    if poetry is not None:
        findings.extend(_template_poetry_violations(module, poetry))
        runtime = _pyproject_table(poetry, "dependencies")
        if runtime is not None:
            findings.extend(_template_runtime_violations(module, runtime))
        dev = _pyproject_table(poetry, "group.dev.dependencies")
        if dev is not None:
            findings.extend(_template_dev_violations(module, dev))
        extras = _pyproject_table(poetry, "extras")
        if extras is not None:
            findings.extend(_template_extras_violations(module, extras))
    for path, expected in PYPROJECT_TEMPLATE_TABLE_VALUES:
        table = _pyproject_table(data, path)
        if table is None:
            continue
        findings.extend(_template_value_violations(module.name, path, table, expected))
        findings.extend(
            _template_key_violations(
                module.name, path, table, (*expected, *_template_child_keys(path))
            )
        )
    pytest_table = _pyproject_table(data, "tool.pytest.ini_options")
    if pytest_table is not None:
        findings.extend(_template_pytest_violations(module, pytest_table))
    return findings


def _module_pyproject_violations(module: Module) -> list[str]:
    """Rule 18: one module's pyproject parses and follows the template."""
    text = module.root_files.get("pyproject.toml")
    if text is None:
        return [f"rule 18: {module.name}: missing pyproject.toml"]
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return [f"rule 18: {module.name}: pyproject.toml is invalid: {exc}"]
    return _pyproject_template_violations(module, data, text)
