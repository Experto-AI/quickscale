"""Manifest section parsing for managed files and contract vintages.

Split out of :mod:`quickscale_core.manifest.loader`; the loader facade
re-exports these helpers so existing imports keep working.  This module owns
the ``managed_files``, ``required_modules``, ``contract_vintage``, and
packaged project-contract declaration sections.
"""

from __future__ import annotations

import posixpath
from typing import Any

from quickscale_core.manifest.loader_errors import ManifestError
from quickscale_core.manifest.schema import (
    MANAGED_FILE_ROOT_PREFIX,
    ContractVintage,
    ManagedFileDeclaration,
    ProjectContractStep,
    ProjectContractVintage,
)


def _validate_managed_file_path(
    key: str, output_path: str, module_name: str | None
) -> None:
    """Enforce the managed-file write boundary on one declared path."""
    if not output_path.startswith(MANAGED_FILE_ROOT_PREFIX):
        raise ManifestError(
            f"managed_files.{key}.output_path must start with "
            f"'{MANAGED_FILE_ROOT_PREFIX}' "
            f"(got '{output_path}')",
            module_name,
        )

    # Defense-in-depth: normalize the path to reject traversal attempts
    # like "quickscale_managed/../etc/passwd".
    normalized = posixpath.normpath(output_path)
    if not (
        normalized.startswith(MANAGED_FILE_ROOT_PREFIX)
        or normalized == MANAGED_FILE_ROOT_PREFIX.rstrip("/")
    ):
        raise ManifestError(
            f"managed_files.{key}.output_path resolves outside "
            f"'{MANAGED_FILE_ROOT_PREFIX}' after normalization "
            f"(got '{output_path}')",
            module_name,
        )


def _parse_managed_file_entry(
    key: str, entry: Any, module_name: str | None
) -> ManagedFileDeclaration:
    """Parse and validate one ``managed_files`` entry."""
    if entry is None:
        entry = {}
    if not isinstance(entry, dict):
        raise ManifestError(
            f"managed_files.{key} must be a mapping or empty",
            module_name,
        )

    renderer = entry.get("renderer")
    if not isinstance(renderer, str) or not renderer:
        raise ManifestError(
            f"managed_files.{key}.renderer must be a non-empty string",
            module_name,
        )

    output_path = entry.get("output_path")
    if not isinstance(output_path, str) or not output_path:
        raise ManifestError(
            f"managed_files.{key}.output_path must be a non-empty string",
            module_name,
        )

    _validate_managed_file_path(key, output_path, module_name)

    return ManagedFileDeclaration(
        key=key,
        renderer=renderer,
        output_path=output_path,
    )


def _parse_managed_files(
    data: dict[str, Any], module_name: str | None
) -> dict[str, ManagedFileDeclaration]:
    """Parse and validate the top-level ``managed_files`` section.

    Each entry must be a mapping with at least ``renderer`` (non-empty
    string) and ``output_path`` (non-empty string starting with
    ``quickscale_managed/``).  Entries that violate the write boundary
    raise :class:`ManifestError`.

    Args:
        data: The full parsed YAML data dictionary.
        module_name: Optional module name for error messages.

    Returns:
        A dict mapping managed-file keys to their
        :class:`ManagedFileDeclaration` instances.  Returns an empty
        dict when the section is absent.

    Raises:
        ManifestError: If the section is malformed or a path escapes
            the managed root.
    """
    raw_section = data.get("managed_files")
    if raw_section is None:
        return {}

    if not isinstance(raw_section, dict):
        raise ManifestError("'managed_files' must be a mapping", module_name)

    declarations: dict[str, ManagedFileDeclaration] = {}

    for key, entry in raw_section.items():
        declarations[key] = _parse_managed_file_entry(key, entry, module_name)

    return declarations


def _parse_required_modules(data: dict[str, Any], module_name: str | None) -> list[str]:
    """Validate the optional list of bare required-module names.

    Every entry must be a bare first-party module name (Module Conventions
    rule 39): the ``name>=version`` form and the ``implies`` key are
    retired, and both are refused here by name.  The parser lives in
    :mod:`quickscale_core.manifest.required_modules` (which imports the
    loader facade, so the reference is function-local to avoid a cycle).

    Args:
        data: The full parsed YAML data dictionary.
        module_name: Optional module name for error messages.

    Returns:
        The declared bare module names, in declaration order.

    Raises:
        ManifestError: If the entry list or any entry is malformed, or if
            the retired ``implies`` key is present.
    """
    from quickscale_core.manifest.required_modules import (  # noqa: PLC0415
        parse_required_module_entry,
    )

    if "implies" in data:
        raise ManifestError(
            "'implies' is retired: declare the dependency in "
            "'required_modules' as a bare module name "
            "(Module Conventions rule 39).",
            module_name,
        )

    value = data.get("required_modules", [])
    if not isinstance(value, list):
        raise ManifestError("'required_modules' must be a list", module_name)
    return [parse_required_module_entry(entry, module_name) for entry in value]


def _validate_declared_minimum(
    minimum: object,
    label: str,
    module_name: str | None = None,
) -> str:
    """Validate a declared dotted-numeric version string, failing closed.

    A malformed value like ``"abc"`` would parse as ``(0,)`` via
    ``parse_version_tuple`` and fail open, so it is rejected at load time.
    """
    if not isinstance(minimum, str) or not minimum:
        raise ManifestError(f"{label} must be a non-empty string", module_name)
    try:
        core = minimum.split("-")[0]
        [int(p) for p in core.split(".")]
    except ValueError, AttributeError:
        raise ManifestError(
            f"{label} must be a valid dotted-numeric version string (e.g. '0.89.0')",
            module_name,
        )
    return minimum


def _parse_contract_vintage(
    data: dict[str, Any],
    module_name: str | None,
) -> ContractVintage | None:
    """Parse the optional ``contract_vintage`` section from manifest data.

    Returns a :class:`ContractVintage` instance when the section is present,
    or ``None`` when absent.

    Args:
        data: The full parsed YAML data dictionary.
        module_name: Optional module name for error messages.

    Returns:
        :class:`ContractVintage` or ``None``.

    Raises:
        ManifestError: If the section is malformed.
    """
    raw = data.get("contract_vintage")
    if raw is None:
        return None

    if not isinstance(raw, dict):
        raise ManifestError("'contract_vintage' must be a mapping", module_name)

    minimum = _validate_declared_minimum(
        raw.get("minimum"),
        "'contract_vintage.minimum'",
        module_name,
    )

    steps = _parse_contract_adoption_steps(
        raw.get("manual_adoption_steps", []),
        module_name,
    )

    vintage_id = raw.get("id")
    if vintage_id is not None and (not isinstance(vintage_id, str) or not vintage_id):
        raise ManifestError(
            "'contract_vintage.id' must be a non-empty string",
            module_name,
        )

    return ContractVintage(
        minimum=minimum,
        manual_adoption_steps=steps,
        id=vintage_id,
    )


def _parse_contract_adoption_steps(
    steps_raw: Any, module_name: str | None
) -> list[str]:
    """Parse and validate the contract-vintage manual-adoption-steps list."""
    if steps_raw is None:
        steps_raw = []
    if not isinstance(steps_raw, list):
        raise ManifestError(
            "'contract_vintage.manual_adoption_steps' must be a list",
            module_name,
        )
    steps: list[str] = []
    for i, step in enumerate(steps_raw):
        if not isinstance(step, str):
            raise ManifestError(
                f"'contract_vintage.manual_adoption_steps[{i}]' must be a string",
                module_name,
            )
        steps.append(step)
    return steps


def _validate_project_contract_step_id(raw_step: dict[str, Any], label: str) -> str:
    """Validate one project-contract step's ``id`` and return it."""
    step_id = raw_step.get("id")
    if not isinstance(step_id, str) or not step_id:
        raise ManifestError(f"'{label}.id' must be a non-empty string")
    return step_id


def _parse_project_contract_step_body(
    raw_step: dict[str, Any], label: str, step_id: str
) -> ProjectContractStep:
    """Parse the bodies of one project-contract declaration step."""
    minimum = _validate_declared_minimum(raw_step.get("minimum"), f"'{label}.minimum'")

    title = raw_step.get("title")
    if not isinstance(title, str) or not title:
        raise ManifestError(f"'{label}.title' must be a non-empty string")

    adoption_steps = _parse_required_adoption_steps(
        raw_step.get("adoption_steps"), label
    )

    return ProjectContractStep(
        id=step_id,
        minimum=minimum,
        title=title,
        manual_adoption_steps=adoption_steps,
    )


def _parse_required_adoption_steps(adoption_raw: Any, label: str) -> list[str]:
    """Parse and validate a project-contract step's adoption steps."""
    if not isinstance(adoption_raw, list) or not adoption_raw:
        raise ManifestError(f"'{label}.adoption_steps' must be a non-empty list")
    adoption_steps: list[str] = []
    for j, step in enumerate(adoption_raw):
        if not isinstance(step, str) or not step:
            raise ManifestError(
                f"'{label}.adoption_steps[{j}]' must be a non-empty string"
            )
        adoption_steps.append(step)
    return adoption_steps


def _parse_project_contract_vintage(data: dict[str, Any]) -> ProjectContractVintage:
    """Parse the packaged generated-project contract declaration.

    The declaration is fail-closed: a missing, empty, or malformed ``steps``
    list raises rather than silently disabling enforcement.

    Args:
        data: The full parsed YAML data dictionary.

    Returns:
        :class:`ProjectContractVintage`.

    Raises:
        ManifestError: If the declaration is malformed.
    """
    steps_raw = data.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise ManifestError(
            "'steps' must be a non-empty list in the project contract declaration"
        )

    steps: list[ProjectContractStep] = []
    seen_ids: set[str] = set()
    for i, raw_step in enumerate(steps_raw):
        label = f"steps[{i}]"
        if not isinstance(raw_step, dict):
            raise ManifestError(f"'{label}' must be a mapping")

        step_id = _validate_project_contract_step_id(raw_step, label)
        if step_id in seen_ids:
            raise ManifestError(f"'{label}.id' duplicates {step_id!r}")
        seen_ids.add(step_id)

        steps.append(_parse_project_contract_step_body(raw_step, label, step_id))

    return ProjectContractVintage(steps=steps)
