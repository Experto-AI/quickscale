"""Manifest parsing for a module's generated-project blocks (SA320).

Split out of :mod:`quickscale_core.manifest.loader_sections` so the section's
closed validation stays in a focused sibling while the loader facade re-exports
the parser for existing imports.

A module's ``project_blocks`` section is the single home of the behavior it
contributes to the generated project's user-owned root files.  The generated
``Makefile``, ``.github/workflows/ci.yml``, and ``docker-compose.yml`` carry a
managed region per block, so core names no module and a module release changes
no user-owned file.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from quickscale_core.manifest.loader_errors import ManifestError
from quickscale_core.manifest.schema import MakeTarget, ProjectBlocks

#: The keys a top-level ``project_blocks`` section may declare.
_PROJECT_BLOCK_KEYS = frozenset(
    {
        "ci_steps",
        "ci_jobs",
        "ci_test_env",
        "make_targets",
        "make_test_env",
        "compose_env",
    }
)

#: A make target name.
_MAKE_TARGET_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")

#: Environment-variable names a make test prefix or Compose pass-through may
#: use.
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")

#: A make test-prefix value: one shell assignment value with no whitespace or
#: make/comment metacharacters.
_MAKE_ENV_VALUE = re.compile(r"[A-Za-z0-9_./:@%+-]+\Z")

#: Managed-region markers a declared text block must never carry: a module
#: block that names a marker would terminate or duplicate the region.
_REGION_MARKER = re.compile(r"#\s*(?:End\s+)?QuickScale module\b")

#: Core Makefile targets a module target may not shadow.
_RESERVED_MAKE_TARGETS = frozenset(
    {
        "help",
        "setup",
        "lint",
        "lint-backend",
        "lint-frontend",
        "format",
        "test",
        "test-backend",
        "test-frontend",
        "check",
        "ci",
    }
)


def _validated_text(value: Any, key: str, module_name: str | None) -> str:
    """Return one declared text block after its shape is validated."""
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(
            f"project_blocks.{key} must be a non-empty string",
            module_name,
        )
    if "\x00" in value or "\r" in value:
        raise ManifestError(
            f"project_blocks.{key} must not contain NUL or carriage-return characters",
            module_name,
        )
    if _REGION_MARKER.search(value):
        raise ManifestError(
            f"project_blocks.{key} must not contain a managed-region marker",
            module_name,
        )
    return value


def _parse_make_target(
    entry: Any,
    index: int,
    module_name: str | None,
    seen: set[str],
) -> MakeTarget:
    """Parse and validate one ``make_targets`` entry."""
    if not isinstance(entry, dict):
        raise ManifestError(
            f"project_blocks.make_targets[{index}] must be a mapping",
            module_name,
        )
    unknown = set(entry) - {"name", "help", "recipe"}
    if unknown:
        allowed = ", ".join(sorted({"name", "help", "recipe"}))
        raise ManifestError(
            f"project_blocks.make_targets[{index}] declares unknown key "
            f"'{sorted(unknown)[0]}' (allowed: {allowed})",
            module_name,
        )
    name = entry.get("name")
    if not isinstance(name, str) or _MAKE_TARGET_NAME.fullmatch(name) is None:
        raise ManifestError(
            f"project_blocks.make_targets[{index}].name must be a make target name",
            module_name,
        )
    if name in _RESERVED_MAKE_TARGETS:
        raise ManifestError(
            f"project_blocks.make_targets[{index}].name '{name}' shadows a "
            "core Makefile target",
            module_name,
        )
    if name in seen:
        raise ManifestError(
            f"project_blocks.make_targets declares duplicate target '{name}'",
            module_name,
        )
    seen.add(name)
    help_text = entry.get("help")
    if (
        not isinstance(help_text, str)
        or not help_text.strip()
        or "\n" in help_text
        or "\r" in help_text
        or "#" in help_text
    ):
        raise ManifestError(
            f"project_blocks.make_targets[{index}].help must be one line with no '#'",
            module_name,
        )
    recipe = entry.get("recipe")
    if not isinstance(recipe, list) or not recipe:
        raise ManifestError(
            f"project_blocks.make_targets[{index}].recipe must be a non-empty list",
            module_name,
        )
    for line_index, line in enumerate(recipe):
        if (
            not isinstance(line, str)
            or not line.strip()
            or "\n" in line
            or "\r" in line
        ):
            raise ManifestError(
                f"project_blocks.make_targets[{index}].recipe[{line_index}] must be "
                "one non-empty line",
                module_name,
            )
    return MakeTarget(name=name, help=help_text.strip(), recipe=tuple(recipe))


def _parse_make_targets(
    raw_targets: Any, module_name: str | None
) -> tuple[MakeTarget, ...]:
    """Parse and validate the ``make_targets`` list."""
    if not isinstance(raw_targets, list):
        raise ManifestError("project_blocks.make_targets must be a list", module_name)
    seen: set[str] = set()
    return tuple(
        _parse_make_target(entry, index, module_name, seen)
        for index, entry in enumerate(raw_targets)
    )


def _parse_make_test_env(raw_env: Any, module_name: str | None) -> dict[str, str]:
    """Parse and validate the ``make_test_env`` mapping."""
    if not isinstance(raw_env, dict):
        raise ManifestError(
            "project_blocks.make_test_env must be a mapping", module_name
        )
    env: dict[str, str] = {}
    for name, value in raw_env.items():
        if not isinstance(name, str) or _ENV_NAME.fullmatch(name) is None:
            raise ManifestError(
                "project_blocks.make_test_env keys must be environment-variable names",
                module_name,
            )
        if not isinstance(value, str) or _MAKE_ENV_VALUE.fullmatch(value) is None:
            raise ManifestError(
                f"project_blocks.make_test_env.{name} must be a single shell "
                "value with no whitespace",
                module_name,
            )
        env[name] = value
    return env


def _parse_compose_env(
    raw_options: Any,
    module_name: str | None,
    options: Mapping[str, Any],
) -> tuple[str, ...]:
    """Parse and validate the ``compose_env`` option-name list."""
    if not isinstance(raw_options, list):
        raise ManifestError("project_blocks.compose_env must be a list", module_name)
    declared: list[str] = []
    for index, option_name in enumerate(raw_options):
        if not isinstance(option_name, str) or not option_name:
            raise ManifestError(
                f"project_blocks.compose_env[{index}] must be an option name",
                module_name,
            )
        option = options.get(option_name)
        if option is None:
            raise ManifestError(
                f"project_blocks.compose_env[{index}] '{option_name}' does not "
                "name a declared option",
                module_name,
            )
        if option.option_type != "string":
            raise ManifestError(
                f"project_blocks.compose_env[{index}] '{option_name}' must name "
                f"a string option (got type '{option.option_type}')",
                module_name,
            )
        if not option.django_setting.endswith("_ENV_VAR"):
            raise ManifestError(
                f"project_blocks.compose_env[{index}] '{option_name}' must name "
                "an option whose django_setting ends in '_ENV_VAR' (its resolved "
                "value is the environment-variable name to pass through)",
                module_name,
            )
        if option_name in declared:
            raise ManifestError(
                f"project_blocks.compose_env declares duplicate option '{option_name}'",
                module_name,
            )
        declared.append(option_name)
    return tuple(declared)


def _parse_ci_test_env(raw_env: Any, module_name: str | None) -> dict[str, str]:
    """Parse and validate the ``ci_test_env`` mapping."""
    if not isinstance(raw_env, dict):
        raise ManifestError("project_blocks.ci_test_env must be a mapping", module_name)
    env: dict[str, str] = {}
    for name, value in raw_env.items():
        if not isinstance(name, str) or _ENV_NAME.fullmatch(name) is None:
            raise ManifestError(
                "project_blocks.ci_test_env keys must be environment-variable names",
                module_name,
            )
        if not isinstance(value, str) or _MAKE_ENV_VALUE.fullmatch(value) is None:
            raise ManifestError(
                f"project_blocks.ci_test_env.{name} must be a single YAML-safe value",
                module_name,
            )
        env[name] = value
    return env


def _parse_project_blocks(
    data: dict[str, Any],
    module_name: str | None,
    options: Mapping[str, Any],
) -> ProjectBlocks | None:
    """Parse and validate the optional top-level ``project_blocks`` section.

    Args:
        data: The full parsed YAML data dictionary.
        module_name: Optional module name for error messages.
        options: The manifest's declared options (mutable and immutable).

    Returns:
        The validated :class:`ProjectBlocks`, or ``None`` when the section is
        absent.

    Raises:
        ManifestError: If the section is not a mapping, declares an unknown
            key, or a value is malformed.
    """
    raw_section = data.get("project_blocks")
    if raw_section is None:
        return None
    if not isinstance(raw_section, dict):
        raise ManifestError("'project_blocks' must be a mapping", module_name)
    unknown = set(raw_section) - _PROJECT_BLOCK_KEYS
    if unknown:
        allowed = ", ".join(sorted(_PROJECT_BLOCK_KEYS))
        raise ManifestError(
            f"project_blocks declares unknown key '{sorted(unknown)[0]}' "
            f"(allowed: {allowed})",
            module_name,
        )
    if not raw_section:
        raise ManifestError(
            "project_blocks must declare at least one block",
            module_name,
        )

    ci_steps = (
        _validated_text(raw_section["ci_steps"], "ci_steps", module_name)
        if "ci_steps" in raw_section
        else None
    )
    ci_jobs = (
        _validated_text(raw_section["ci_jobs"], "ci_jobs", module_name)
        if "ci_jobs" in raw_section
        else None
    )
    make_targets = (
        _parse_make_targets(raw_section["make_targets"], module_name)
        if "make_targets" in raw_section
        else ()
    )
    make_test_env = (
        _parse_make_test_env(raw_section["make_test_env"], module_name)
        if "make_test_env" in raw_section
        else {}
    )
    compose_env = (
        _parse_compose_env(raw_section["compose_env"], module_name, options)
        if "compose_env" in raw_section
        else ()
    )
    ci_test_env = (
        _parse_ci_test_env(raw_section["ci_test_env"], module_name)
        if "ci_test_env" in raw_section
        else {}
    )
    return ProjectBlocks(
        ci_steps=ci_steps,
        ci_jobs=ci_jobs,
        make_targets=make_targets,
        make_test_env=make_test_env,
        compose_env=compose_env,
        ci_test_env=ci_test_env,
    )
