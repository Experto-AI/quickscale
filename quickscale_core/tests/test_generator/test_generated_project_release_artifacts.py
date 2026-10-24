"""Regression tests for the generated project's release artifacts.

These hold the defect classes closed by SA312: the rendered README must not
present the development Compose stack as production, its YAML examples must
parse, its commands must not overwrite a generated file, the rendered Docker
build must not carry local backups, the rendered dependencies must declare the
Redis cache client, and every action in the rendered CI workflow must stay
pinned by full commit SHA.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

import quickscale_core
from quickscale_core.generator.generator import get_generator_emission_mapping
from quickscale_core.generator.runtime_database import runtime_db_template_context
from quickscale_core.generator.runtime_pins import (
    DJANGO_CI_MATRIX_VERSION,
    DJANGO_CONSTRAINT,
    POSTGRES_PATCH_VERSION,
    POSTGRES_VERSION,
    PYTHON_CONSTRAINT,
    PYTHON_PATCH_VERSION,
    PYTHON_VERSION,
    QUICKSCALE_CORE_PIN,
)

_TEMPLATE_DIR = (
    Path(quickscale_core.__file__).resolve().parent / "generator" / "templates"
)

# ``owner/repo@<40 hex characters>``; a mutable tag such as ``@v6`` fails.
_PINNED_ACTION = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")

_WRITE_VERBS = frozenset({"cp", "mv", "tee"})
_REDIRECT = re.compile(r"(?<!>)>{1,2}\s*([^\s;|&]+)")


def _render(template_name: str, **overrides: object) -> str:
    """Render one generated-project template with the generator's sample context."""
    environment = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        keep_trailing_newline=True,
    )
    context: dict[str, object] = {
        "project_name": "testproject",
        "package_name": "testproject",
        "theme": "showcase_react",
        "python_version": PYTHON_VERSION,
        "python_patch_version": PYTHON_PATCH_VERSION,
        "python_constraint": PYTHON_CONSTRAINT,
        "django_constraint": DJANGO_CONSTRAINT,
        "django_ci_version": DJANGO_CI_MATRIX_VERSION,
        "postgres_version": POSTGRES_VERSION,
        "postgres_patch_version": POSTGRES_PATCH_VERSION,
        "quickscale_core_pin": QUICKSCALE_CORE_PIN,
        **runtime_db_template_context("testproject"),
        "selected_modules": None,
    }
    context.update(overrides)
    return environment.get_template(template_name).render(context)


def _fenced_blocks(markdown: str, language: str) -> list[str]:
    """Return the contents of every fenced code block in *language*."""
    pattern = re.compile(rf"```{language}\n(.*?)```", re.DOTALL)
    return pattern.findall(markdown)


def _write_destinations(command_block: str) -> set[str]:
    """Return every path an example command writes, without executing it."""
    destinations: set[str] = set()
    for line in command_block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            tokens = shlex.split(stripped, comments=True)
        except ValueError:
            continue
        for index, token in enumerate(tokens):
            if token not in _WRITE_VERBS:
                continue
            operands = [
                operand
                for operand in tokens[index + 1 :]
                if not operand.startswith("-")
            ]
            if token == "tee":
                destinations.update(operands)
            elif len(operands) >= 2:
                destinations.add(operands[-1])
        for match in _REDIRECT.finditer(stripped):
            destination = match.group(1)
            if not destination.startswith("$"):
                destinations.add(destination)
    return destinations


def _normalize(path: str) -> str:
    """Normalize a project-relative path for comparison with emitted paths."""
    return path.strip("'\"").removeprefix("./").rstrip("/")


def test_write_destination_scanner_detects_a_clobbering_example() -> None:
    """Control: the scanner catches the ``.env`` overwrite this change removes."""
    assert _write_destinations("cp .env.example .env\n") == {".env"}


def test_every_rendered_readme_yaml_block_parses() -> None:
    """A generated README example must be valid YAML, not tab-indented text."""
    blocks = _fenced_blocks(_render("README.md.j2"), "yaml")

    assert blocks, "expected at least one fenced yaml example"
    for block in blocks:
        parsed = yaml.safe_load(block)
        assert isinstance(parsed, dict)


def test_rendered_readme_examples_do_not_overwrite_generated_files() -> None:
    """No rendered example may copy over a file the generator already emitted."""
    generated = {
        _normalize(path) for path in get_generator_emission_mapping(_TEMPLATE_DIR)
    }
    assert ".env" in generated

    clobbered: set[str] = set()
    for block in _fenced_blocks(_render("README.md.j2"), "bash"):
        clobbered.update(
            destination
            for destination in _write_destinations(block)
            if _normalize(destination) in generated
        )

    assert clobbered == set(), (
        "README examples overwrite generated files: " + ", ".join(sorted(clobbered))
    )


def test_rendered_readme_labels_compose_as_local_development() -> None:
    """The development Compose stack must not be presented as production."""
    output = _render("README.md.j2")

    assert "are ready for production use" not in output
    dock_section = " ".join(
        output.split("### Docker (Local Development)", 1)[1].split()
    )
    assert "`docker-compose.yml` is a" in dock_section
    assert "local development stack" in dock_section
    assert "not a production deployment" in dock_section


def test_rendered_dockerignore_excludes_backups_but_keeps_the_wheel_cache() -> None:
    """Local dumps stay out of the image; the local-wheel cache stays in."""
    entries = {
        line.strip()
        for line in _render(".dockerignore.j2").splitlines()
        if line.strip() and not line.startswith("#")
    }

    assert ".quickscale/backups/" in entries
    assert ".quickscale/*.lock" in entries
    # A project pinned to a locally built quickscale-core wheel installs from
    # `.quickscale/wheels/`, so the whole directory must not be excluded.
    assert ".quickscale/" not in entries
    assert ".quickscale/wheels/" not in entries
    assert "COPY . ." in _render("Dockerfile.j2")


def test_rendered_gitignore_ignores_the_vite_build_output() -> None:
    """A Vite build lands in ``static/frontend/`` and must not dirty the tree."""
    entries = {
        line.strip()
        for line in _render(".gitignore.j2").splitlines()
        if line.strip() and not line.startswith("#")
    }

    assert "/static/frontend/" in entries


def test_rendered_pyproject_declares_the_redis_cache_client() -> None:
    """RedisCache needs the redis client in the runtime dependency group."""
    output = _render("pyproject.toml.j2")
    runtime_dependencies = output.split("[tool.poetry.group.dev.dependencies]", 1)[0]

    assert re.search(r'^redis = "\^[0-9]', runtime_dependencies, re.MULTILINE)


def test_rendered_ci_workflow_pins_every_action_by_full_sha() -> None:
    """Every ``uses:`` must name a 40-hex commit, never a mutable tag."""
    workflow = yaml.safe_load(_render("github/workflows/ci.yml.j2"))
    references = [
        step["uses"]
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if "uses" in step
    ]

    assert references
    for reference in references:
        assert _PINNED_ACTION.fullmatch(reference), (
            f"unpinned action reference: {reference}"
        )
