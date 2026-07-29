"""Drift detection for runtime-pin constraints across the repository.

This module validates that generator repo files, embedded module
``pyproject.toml`` files, and the generated-project SSOT
(:mod:`quickscale_core.generator.runtime_pins`) remain in the expected
relationship defined by the F7.2/F7.3 contract:

* All generator Python constraints must match
  :data:`runtime_pins.PYTHON_CONSTRAINT`.
* All packaged-module Python constraints must match
  :data:`runtime_pins.PYTHON_CONSTRAINT`.
* All packaged-module Django constraints must equal the expected module
  Django constraint, which shares the same upper bound as
  :data:`runtime_pins.DJANGO_CONSTRAINT`.  The module lower bound is
  allowed to be tighter than the template's; it is passed in by the
  caller rather than derived, so any divergence has to be stated
  explicitly.  As of the 6.0.7 bump the two bounds coincide.

Each public function returns a list of human-readable drift messages
(empty list = all constraints pass).  Callers should treat any non-empty
result as a failure.
"""

import tomllib
from pathlib import Path
from typing import Sequence

# ── Helpers ──────────────────────────────────────────────────────────

# Generator packages that participate in the Python-constraint parity check.
_GENERATOR_PACKAGES: Sequence[str] = (
    "pyproject.toml",  # root monorepo
    "quickscale/pyproject.toml",
    "quickscale_core/pyproject.toml",
    "quickscale_cli/pyproject.toml",
)

# Packaged module directories whose ``pyproject.toml`` is expected to
# carry runtime-pin constraints.  Non-packaged directories such as
# ``teams/`` (placeholder-only) and ``README.md`` are skipped
# automatically because they lack a ``pyproject.toml``.
_MODULES_ROOT_REL = "quickscale_modules"


def _parse_requires_python(filepath: Path) -> str | None:
    """Extract ``requires-python`` from the PEP 621 ``[project]`` table."""
    with filepath.open("rb") as fh:
        data = tomllib.load(fh)
    project = data.get("project", {})
    return project.get("requires-python")  # type: ignore[no-any-return]


def _parse_poetry_dependency(filepath: Path, dep_name: str) -> str | None:
    """Extract a Poetry dependency constraint string by name."""
    with filepath.open("rb") as fh:
        data = tomllib.load(fh)
    tool = data.get("tool", {})
    poetry = tool.get("poetry", {})
    deps = poetry.get("dependencies", {})
    dep = deps.get(dep_name)
    if isinstance(dep, str):
        return dep
    return None


# ── Generator-package Python constraints ─────────────────────────────


def check_generator_python_constraints(
    repo_root: Path,
    expected_python: str,
) -> list[str]:
    """Verify all generator ``requires-python`` matches *expected_python*.

    Parameters
    ----------
    repo_root:
        Absolute path to the repository root (containing the top-level
        ``pyproject.toml``).
    expected_python:
        The constraint string that every generator package must carry
        (typically :data:`runtime_pins.PYTHON_CONSTRAINT`).

    Returns
    -------
    list[str]
        Drift messages, or an empty list if all constraints are correct.
    """
    messages: list[str] = []
    for rel in _GENERATOR_PACKAGES:
        fp = repo_root / rel
        if not fp.exists():
            messages.append(f"MISSING: {rel} — file not found at {fp}")
            continue
        actual = _parse_requires_python(fp)
        if actual is None:
            messages.append(f"NO requires-python in {rel}")
        elif actual != expected_python:
            messages.append(
                f"DRIFT: {rel} requires-python is {actual!r}, "
                f"expected {expected_python!r}"
            )
    return messages


# ── Packaged-module Python constraints ───────────────────────────────


def check_module_python_constraints(
    repo_root: Path,
    expected_python: str,
) -> list[str]:
    """Verify all packaged modules ``requires-python`` matches *expected_python*.

    Parameters
    ----------
    repo_root:
        Absolute path to the repository root.
    expected_python:
        The constraint string that every packaged module must carry
        (typically :data:`runtime_pins.PYTHON_CONSTRAINT`).

    Returns
    -------
    list[str]
        Drift messages, or an empty list if all constraints are correct.
    """
    messages: list[str] = []
    modules_root = repo_root / _MODULES_ROOT_REL
    if not modules_root.is_dir():
        messages.append(f"MISSING: {_MODULES_ROOT_REL}/ directory not found")
        return messages

    for child in sorted(modules_root.iterdir()):
        pyproject = child / "pyproject.toml"
        if not pyproject.is_file():
            continue  # skip non-package entries (README.md, teams/, etc.)

        actual = _parse_requires_python(pyproject)
        if actual is None:
            messages.append(
                f"NO requires-python in {_MODULES_ROOT_REL}/{child.name}/pyproject.toml"
            )
        elif actual != expected_python:
            messages.append(
                f"DRIFT: {_MODULES_ROOT_REL}/{child.name}/pyproject.toml "
                f"requires-python is {actual!r}, expected {expected_python!r}"
            )
    return messages


# ── Generator-package Poetry python constraints ──────────────────────


def check_generator_poetry_python_constraints(
    repo_root: Path,
    expected_python: str,
) -> list[str]:
    """Verify generator ``[tool.poetry.dependencies] python`` matches *expected_python*.

    Like :func:`check_generator_python_constraints` but validates the
    Poetry dependency surface rather than the PEP 621 ``requires-python``
    field.  Both must stay in sync with
    :data:`runtime_pins.PYTHON_CONSTRAINT`.

    Parameters
    ----------
    repo_root:
        Absolute path to the repository root.
    expected_python:
        The constraint string every generator package must carry in its
        Poetry python dependency.

    Returns
    -------
    list[str]
        Drift messages, or an empty list if all constraints are correct.
    """
    messages: list[str] = []
    for rel in _GENERATOR_PACKAGES:
        fp = repo_root / rel
        if not fp.exists():
            messages.append(f"MISSING: {rel} — file not found at {fp}")
            continue
        actual = _parse_poetry_dependency(fp, "python")
        if actual is None:
            messages.append(f"NO poetry python dependency in {rel}")
        elif actual != expected_python:
            messages.append(
                f"DRIFT: {rel} tool.poetry.dependencies.python is {actual!r}, "
                f"expected {expected_python!r}"
            )
    return messages


# ── Packaged-module Poetry python constraints ────────────────────────


def check_module_poetry_python_constraints(
    repo_root: Path,
    expected_python: str,
) -> list[str]:
    """Verify module ``[tool.poetry.dependencies] python`` matches *expected_python*.

    Like :func:`check_module_python_constraints` but validates the Poetry
    dependency surface rather than the PEP 621 ``requires-python`` field.
    Both must stay in sync with
    :data:`runtime_pins.PYTHON_CONSTRAINT`.

    Parameters
    ----------
    repo_root:
        Absolute path to the repository root.
    expected_python:
        The constraint string every packaged module must carry in its
        Poetry python dependency.

    Returns
    -------
    list[str]
        Drift messages, or an empty list if all constraints are correct.
    """
    messages: list[str] = []
    modules_root = repo_root / _MODULES_ROOT_REL
    if not modules_root.is_dir():
        messages.append(f"MISSING: {_MODULES_ROOT_REL}/ directory not found")
        return messages

    for child in sorted(modules_root.iterdir()):
        pyproject = child / "pyproject.toml"
        if not pyproject.is_file():
            continue

        actual = _parse_poetry_dependency(pyproject, "python")
        if actual is None:
            messages.append(
                f"NO poetry python dependency in "
                f"{_MODULES_ROOT_REL}/{child.name}/pyproject.toml"
            )
        elif actual != expected_python:
            messages.append(
                f"DRIFT: {_MODULES_ROOT_REL}/{child.name}/pyproject.toml "
                f"tool.poetry.dependencies.python is {actual!r}, "
                f"expected {expected_python!r}"
            )
    return messages


# ── Packaged-module Django constraints ───────────────────────────────


def check_module_django_constraints(
    repo_root: Path,
    expected_django: str,
) -> list[str]:
    """Verify module Django constraints match the expected tighter constraint.

    All packaged modules must carry Django with *expected_django*, which
    allows an intentionally tighter lower bound than the template while
    sharing :data:`runtime_pins.DJANGO_CONSTRAINT`'s upper bound
    (``<6.1.0``).

    Parameters
    ----------
    repo_root:
        Absolute path to the repository root.
    expected_django:
        The full Django constraint string that every packaged module must
        carry (e.g. ``>=6.0.7,<6.1.0``).

    Returns
    -------
    list[str]
        Drift messages, or an empty list if all constraints are correct.
    """
    messages: list[str] = []
    modules_root = repo_root / _MODULES_ROOT_REL
    if not modules_root.is_dir():
        messages.append(f"MISSING: {_MODULES_ROOT_REL}/ directory not found")
        return messages

    for child in sorted(modules_root.iterdir()):
        pyproject = child / "pyproject.toml"
        if not pyproject.is_file():
            continue

        actual = _parse_poetry_dependency(pyproject, "Django")
        if actual is None:
            messages.append(
                f"NO Django dependency in {_MODULES_ROOT_REL}/{child.name}/pyproject.toml"
            )
            continue
        if actual != expected_django:
            messages.append(
                f"DRIFT: {_MODULES_ROOT_REL}/{child.name}/pyproject.toml "
                f"Django constraint is {actual!r}, expected {expected_django!r}"
            )
    return messages
