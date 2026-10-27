"""Managed generated-project regions for module-declared blocks (SA320).

The generated project's ``Makefile``, ``.github/workflows/ci.yml``, and
``docker-compose.yml`` are user-owned.  Each carries one or more marker-paired
managed regions; every installed module's ``project_blocks`` declaration
renders into the matching region.  Core therefore names no module, and
``quickscale apply``/``update``/``remove`` refresh the regions from the
installed manifests without rewriting the user-owned lines around them.

Generation emits the same region content the CLI recomputes, so a fresh
project and an applied one agree byte for byte for the same module set and
options.

Regions are delimited by::

    # QuickScale module make targets (managed)
    ...
    # End QuickScale module make targets

The marker's leading whitespace is the region's indentation; rendered content
is indented to match.  A project generated before this contract has no
markers, so the sync leaves it untouched (the contract-vintage step documents
the one-time adoption).  A file carrying only one of a pair fails explicitly
instead of silently leaving a half-written region.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quickscale_core.contracts.module_catalog import MODULE_CATALOG
from quickscale_core.contracts.resolvers import (
    load_module_manifest_with_fallback,
    resolve_manifest_module_options,
)
from quickscale_core.generator.runtime_pins import (
    DJANGO_CI_MATRIX_VERSION,
    POSTGRES_PATCH_VERSION,
    POSTGRES_VERSION,
    PYTHON_PATCH_VERSION,
)

__all__ = [
    "CI_JOBS_REGION_TITLE",
    "CI_TEST_ENV_REGION_TITLE",
    "CI_STEPS_REGION_TITLE",
    "CI_WORKFLOW_RELATIVE_PATH",
    "COMPOSE_REGION_TITLE",
    "COMPOSE_RELATIVE_PATH",
    "MAKEFILE_RELATIVE_PATH",
    "MAKE_REGION_TITLE",
    "PROJECT_BLOCK_TOKENS",
    "ManagedRegion",
    "ProjectBlockContent",
    "ProjectBlockRegionError",
    "REGIONS",
    "managed_region_paths",
    "restore_managed_region_content",
    "strip_managed_region_content",
    "render_project_block_content",
    "sync_project_block_regions",
]

MAKEFILE_RELATIVE_PATH = "Makefile"
CI_WORKFLOW_RELATIVE_PATH = ".github/workflows/ci.yml"
COMPOSE_RELATIVE_PATH = "docker-compose.yml"

MAKE_REGION_TITLE = "module make targets"
CI_TEST_ENV_REGION_TITLE = "module CI environment"
CI_STEPS_REGION_TITLE = "module CI steps"
CI_JOBS_REGION_TITLE = "module CI jobs"
COMPOSE_REGION_TITLE = "module environment"

#: The project-context tokens a declared text block may carry.
PROJECT_BLOCK_TOKENS = frozenset(
    {
        "package_name",
        "postgres_version",
        "postgres_patch_version",
        "python_patch_version",
        "django_ci_version",
    }
)

_TOKEN = re.compile(r"\{([a-z][a-z0-9_]*)\}")


class ProjectBlockRegionError(RuntimeError):
    """A user-owned file carries an incomplete or malformed managed region."""


@dataclass(frozen=True)
class ProjectBlockContent:
    """The rendered content of each generated-project managed region."""

    make: str = ""
    ci_test_env: str = ""
    ci_steps: str = ""
    ci_jobs: str = ""
    compose_environment: str = ""


@dataclass(frozen=True)
class ManagedRegion:
    """One marker-paired managed region in a generated user-owned file."""

    relative_path: str
    title: str
    content_attribute: str

    @property
    def start_marker(self) -> str:
        """The region's start marker text."""
        return f"# QuickScale {self.title} (managed)"

    @property
    def end_marker(self) -> str:
        """The region's end marker text."""
        return f"# End QuickScale {self.title}"


#: Every generated-project managed region, in the order a sync visits them.
REGIONS: tuple[ManagedRegion, ...] = (
    ManagedRegion(MAKEFILE_RELATIVE_PATH, MAKE_REGION_TITLE, "make"),
    ManagedRegion(CI_WORKFLOW_RELATIVE_PATH, CI_TEST_ENV_REGION_TITLE, "ci_test_env"),
    ManagedRegion(CI_WORKFLOW_RELATIVE_PATH, CI_STEPS_REGION_TITLE, "ci_steps"),
    ManagedRegion(CI_WORKFLOW_RELATIVE_PATH, CI_JOBS_REGION_TITLE, "ci_jobs"),
    ManagedRegion(COMPOSE_RELATIVE_PATH, COMPOSE_REGION_TITLE, "compose_environment"),
)


def strip_managed_region_content(text: str) -> str:
    """Return *text* with each complete managed region's body removed.

    The marker lines stay, so two versions that differ only in managed region
    content compare equal while any change outside the markers or to the
    marker structure compares different.  This lets recovery distinguish a
    transaction-generated region change from an operator edit to the
    user-owned content around it.
    """
    updated = text
    for region in REGIONS:
        lines = updated.splitlines(keepends=True)
        starts = [
            index
            for index, line in enumerate(lines)
            if line.strip() == region.start_marker
        ]
        ends = [
            index
            for index, line in enumerate(lines)
            if line.strip() == region.end_marker
        ]
        if len(starts) != 1 or len(ends) != 1 or ends[0] <= starts[0]:
            continue
        updated = "".join(lines[: starts[0] + 1] + lines[ends[0] :])
    return updated


def restore_managed_region_content(current: str, baseline: str) -> str:
    """Return *current* with each managed region body replaced by *baseline*'s.

    Outside-region content in *current* is preserved.  The two texts must
    carry the same complete marker pair for every region; a missing or
    malformed region in either side raises instead of guessing, so a caller
    can validate before mutating anything.

    Raises:
        ProjectBlockRegionError: When a region's marker pair is missing,
            duplicated, or out of order in either text.
    """
    updated = current
    for region in REGIONS:
        current_lines = updated.splitlines(keepends=True)
        baseline_lines = baseline.splitlines(keepends=True)
        current_starts = [
            index
            for index, line in enumerate(current_lines)
            if line.strip() == region.start_marker
        ]
        current_ends = [
            index
            for index, line in enumerate(current_lines)
            if line.strip() == region.end_marker
        ]
        baseline_starts = [
            index
            for index, line in enumerate(baseline_lines)
            if line.strip() == region.start_marker
        ]
        baseline_ends = [
            index
            for index, line in enumerate(baseline_lines)
            if line.strip() == region.end_marker
        ]
        if (
            not current_starts
            and not current_ends
            and not baseline_starts
            and not baseline_ends
        ):
            continue
        if (
            len(current_starts) != 1
            or len(current_ends) != 1
            or len(baseline_starts) != 1
            or len(baseline_ends) != 1
            or current_ends[0] <= current_starts[0]
            or baseline_ends[0] <= baseline_starts[0]
        ):
            raise ProjectBlockRegionError(
                f"managed region {region.title!r} is missing or malformed in the "
                "current or baseline file"
            )
        baseline_body = baseline_lines[baseline_starts[0] + 1 : baseline_ends[0]]
        updated = "".join(
            current_lines[: current_starts[0] + 1]
            + baseline_body
            + current_lines[current_ends[0] :]
        )
    return updated


def managed_region_paths() -> tuple[str, ...]:
    """Return the project-relative files that carry managed module regions."""
    return tuple(sorted({region.relative_path for region in REGIONS}))


def _selected_module_names(module_names: Iterable[str] | None) -> list[str]:
    """Return the selected module names in deterministic order."""
    if module_names is None:
        names = [entry.name for entry in MODULE_CATALOG]
    else:
        names = list(module_names)
    return sorted(dict.fromkeys(names))


def _context_tokens(package_name: str) -> dict[str, str]:
    """Return the project-context tokens a declared text block may use."""
    return {
        "package_name": package_name,
        "postgres_version": POSTGRES_VERSION,
        "postgres_patch_version": POSTGRES_PATCH_VERSION,
        "python_patch_version": PYTHON_PATCH_VERSION,
        "django_ci_version": DJANGO_CI_MATRIX_VERSION,
    }


def _substitute_tokens(
    text: str,
    tokens: Mapping[str, str],
    module_name: str,
) -> str:
    """Resolve ``{token}`` references in one module's declared text block.

    Only the project-context tokens documented on
    :class:`~quickscale_core.manifest.schema.ProjectBlocks` are known.  An
    unknown lowercase-brace token fails hard instead of leaking a literal
    placeholder into the generated workflow.

    Raises:
        ValueError: When the text references an unknown token.
    """
    pieces: list[str] = []
    cursor = 0
    for match in _TOKEN.finditer(text):
        # A shell or GitHub expression reference (``${name}``, ``${{ ... }}``)
        # is runtime syntax in the module's own block, not a project token.
        if match.start() > 0 and text[match.start() - 1] == "$":
            continue
        token = match.group(1)
        if token not in PROJECT_BLOCK_TOKENS:
            raise ValueError(
                f"{module_name}.project_blocks references unknown project token "
                f"{{{token}}}; allowed tokens: "
                f"{', '.join(sorted(PROJECT_BLOCK_TOKENS))}"
            )
        pieces.append(text[cursor : match.start()])
        pieces.append(tokens[token])
        cursor = match.end()
    pieces.append(text[cursor:])
    return "".join(pieces)


def _render_make(module_names: list[str]) -> str:
    """Render the managed Makefile region."""
    target_names: list[str] = []
    sections: list[str] = []
    test_env: dict[str, str] = {}
    seen_targets: dict[str, str] = {}
    for module_name in module_names:
        manifest = load_module_manifest_with_fallback(module_name)
        blocks = manifest.project_blocks
        if blocks is None:
            continue
        for target in blocks.make_targets:
            owner = seen_targets.get(target.name)
            if owner is not None:
                raise ValueError(
                    f"make target '{target.name}' is declared by both "
                    f"'{owner}' and '{module_name}'; rename one target"
                )
            seen_targets[target.name] = module_name
            target_names.append(target.name)
        if blocks.make_targets:
            lines = [f"# {module_name} module targets (managed)"]
            for target in blocks.make_targets:
                lines.append(f"{target.name}: ## {target.help}")
                lines.extend(f"\t{line}" for line in target.recipe)
                lines.append("")
            sections.append("\n".join(lines))
        for name, value in blocks.make_test_env.items():
            existing = test_env.get(name)
            if existing is not None and existing != value:
                raise ValueError(
                    f"make test environment variable {name!r} is declared with "
                    f"different values ({existing!r} and {value!r}) by "
                    f"module '{module_name}'"
                )
            test_env[name] = value
    if not target_names and not test_env:
        return ""
    lines = ["# Rendered from each installed module's project_blocks declaration."]
    lines.append(
        "QUICKSCALE_MODULE_PHONY := " + " ".join(target_names)
        if target_names
        else "QUICKSCALE_MODULE_PHONY :="
    )
    if test_env:
        lines.append(
            "QUICKSCALE_TEST_ENV := "
            + " ".join(f"{name}={value}" for name, value in sorted(test_env.items()))
        )
    if sections:
        lines.append("")
        lines.append("\n".join(sections).rstrip("\n"))
    return "\n".join(lines).rstrip("\n") + "\n"


def _render_ci_test_env(module_names: list[str]) -> str:
    """Render the test job's module-declared environment region."""
    entries: dict[str, str] = {}
    for module_name in module_names:
        manifest = load_module_manifest_with_fallback(module_name)
        blocks = manifest.project_blocks
        if blocks is None:
            continue
        for name, value in blocks.ci_test_env.items():
            existing = entries.get(name)
            if existing is not None and existing != value:
                raise ValueError(
                    f"CI test environment variable {name!r} is declared with "
                    f"different values ({existing!r} and {value!r}) by "
                    f"module '{module_name}'"
                )
            entries[name] = value
    if not entries:
        return ""
    return "".join(f'{name}: "{entries[name]}"\n' for name in sorted(entries))


def _render_text_blocks(
    module_names: list[str],
    attribute: str,
    label: str,
    tokens: Mapping[str, str],
) -> str:
    """Render one per-job/per-step CI text-block region."""
    sections: list[str] = []
    for module_name in module_names:
        manifest = load_module_manifest_with_fallback(module_name)
        blocks = manifest.project_blocks
        if blocks is None:
            continue
        text = getattr(blocks, attribute)
        if text is None:
            continue
        resolved = _substitute_tokens(text, tokens, module_name)
        sections.append(f"# {module_name} {label} (managed)\n{resolved.rstrip()}")
    if not sections:
        return ""
    return "\n".join(sections).rstrip("\n") + "\n"


def _render_compose(
    module_names: list[str],
    options: Mapping[str, Mapping[str, Any]],
) -> str:
    """Render the managed Compose backend-environment region."""
    lines: list[str] = []
    seen_names: set[str] = set()
    for module_name in module_names:
        manifest = load_module_manifest_with_fallback(module_name)
        blocks = manifest.project_blocks
        if blocks is None or not blocks.compose_env:
            continue
        resolved = resolve_manifest_module_options(
            module_name, options.get(module_name)
        )
        module_lines: list[str] = []
        for option_name in blocks.compose_env:
            env_name = str(resolved.get(option_name) or "").strip()
            if not env_name or env_name in seen_names:
                continue
            seen_names.add(env_name)
            module_lines.append(f"- {env_name}=${{{env_name}:-}}")
        if module_lines:
            lines.append(f"# {module_name} module environment (managed)")
            lines.extend(module_lines)
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def render_project_block_content(
    module_names: Iterable[str] | None,
    options: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    package_name: str,
) -> ProjectBlockContent:
    """Render every generated-project managed region for one module set.

    Args:
        module_names: The installed module selection; ``None`` means the whole
            shipped set.
        options: Configured module options keyed by module name; a module
            absent from the mapping resolves against its declared defaults.
        package_name: The generated project's Python package name, substituted
            into ``{package_name}`` references in declared text blocks.

    Returns:
        One rendered block per managed region; a region with no contributing
        module is empty.
    """
    names = _selected_module_names(module_names)
    resolved_options = options or {}
    tokens = _context_tokens(package_name)
    return ProjectBlockContent(
        make=_render_make(names),
        ci_test_env=_render_ci_test_env(names),
        ci_steps=_render_text_blocks(names, "ci_steps", "module CI steps", tokens),
        ci_jobs=_render_text_blocks(names, "ci_jobs", "module CI jobs", tokens),
        compose_environment=_render_compose(names, resolved_options),
    )


def _indent_region(content: str, indent: str) -> list[str]:
    """Return region *content* lines prefixed with *indent* (blank lines stay blank)."""
    if not content:
        return []
    return [f"{indent}{line}" if line.strip() else "" for line in content.splitlines()]


def _splice_one_region(
    content: str,
    region: ManagedRegion,
    rendered: str,
    relative_path: str,
) -> tuple[str, bool]:
    """Splice one region into *content*, returning the new text and change flag."""
    lines = content.splitlines()
    start_indexes = [
        index for index, line in enumerate(lines) if line.strip() == region.start_marker
    ]
    end_indexes = [
        index for index, line in enumerate(lines) if line.strip() == region.end_marker
    ]
    if not start_indexes and not end_indexes:
        return content, False
    if len(start_indexes) != 1 or len(end_indexes) != 1:
        raise ProjectBlockRegionError(
            f"{relative_path} must carry exactly one '{region.start_marker}' and "
            f"one '{region.end_marker}' marker; found {len(start_indexes)} and "
            f"{len(end_indexes)}"
        )
    start_index = start_indexes[0]
    end_index = end_indexes[0]
    if end_index <= start_index:
        raise ProjectBlockRegionError(
            f"{relative_path} carries the '{region.end_marker}' marker before its "
            f"'{region.start_marker}' marker"
        )
    start_line = lines[start_index]
    indent = start_line[: len(start_line) - len(start_line.lstrip())]
    replacement = [
        f"{indent}{region.start_marker}",
        *_indent_region(rendered, indent),
        f"{indent}{region.end_marker}",
    ]
    updated = "\n".join([*lines[:start_index], *replacement, *lines[end_index + 1 :]])
    if content.endswith("\n"):
        updated += "\n"
    return updated, updated != content


def sync_project_block_regions(
    project_path: Path | str,
    content: ProjectBlockContent,
) -> list[str]:
    """Refresh every managed region in the generated project's root files.

    A missing file, or a file without the region's marker pair, is left
    untouched: projects generated before the region contract adopt it through
    the recorded contract step, and a project may legitimately have removed a
    user-owned root file.  A half-present marker pair fails explicitly.

    Args:
        project_path: Root of the generated project.
        content: The rendered region content.

    Returns:
        The project-relative paths whose bytes changed, sorted.

    Raises:
        ProjectBlockRegionError: When a marker pair is incomplete.
        OSError: When a present file cannot be read or written.
    """
    base = Path(project_path)
    changed: set[str] = set()
    for region in REGIONS:
        path = base / region.relative_path
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        rendered = getattr(content, region.content_attribute)
        updated, did_change = _splice_one_region(
            original, region, rendered, region.relative_path
        )
        if did_change:
            path.write_text(updated, encoding="utf-8")
            changed.add(region.relative_path)
    return sorted(changed)
