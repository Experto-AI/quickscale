"""Manifest section parsing for managed files and contract vintages.

Split out of :mod:`quickscale_core.manifest.loader`; the loader facade
re-exports these helpers so existing imports keep working.  This module owns
the ``managed_files``, ``ci_env``, ``required_modules``, ``contract_vintage``,
and packaged project-contract declaration sections.
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Mapping
from typing import Any

from quickscale_core.contracts.module_options import (
    ADOPTION_STEP_TOKENS,
    resolve_adoption_step_tokens,
)
from quickscale_core.manifest.loader_errors import ManifestError
from quickscale_core.manifest.schema import (
    MANAGED_FILE_ROOT_PREFIX,
    ConfigOption,
    ContractVintage,
    ManagedFileDeclaration,
    ModuleOperations,
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


def _parse_ci_environment(
    data: dict[str, Any],
    module_name: str | None,
    options: Mapping[str, Any],
) -> dict[str, str]:
    """Parse and validate the optional top-level ``ci_env`` section.

    Each entry declares one non-live CI placeholder for a credential the
    module's startup check reads in CI.  The key names a declared string
    option whose resolved value is the environment-variable name (so a
    project that renames the variable through ``quickscale.yml`` keeps its CI
    working without editing a user-owned file), and the value is the
    placeholder CI sets under that name.  A key that does not name a declared
    string option fails closed: it would silently contribute no variable.

    Args:
        data: The full parsed YAML data dictionary.
        module_name: Optional module name for error messages.
        options: The manifest's declared options (mutable and immutable).

    Returns:
        A dict mapping option names to placeholder values.  Returns an empty
        dict when the section is absent.

    Raises:
        ManifestError: If the section is not a mapping, a key does not name a
            declared string option, or a value is not a non-empty string.
    """
    raw_section = data.get("ci_env")
    if raw_section is None:
        return {}

    if not isinstance(raw_section, dict):
        raise ManifestError("'ci_env' must be a mapping", module_name)

    declarations: dict[str, str] = {}
    for option_name, placeholder in raw_section.items():
        if not isinstance(option_name, str) or not option_name:
            raise ManifestError(
                "'ci_env' keys must be non-empty option names",
                module_name,
            )
        option = options.get(option_name)
        if option is None:
            raise ManifestError(
                f"ci_env.{option_name} does not name a declared option",
                module_name,
            )
        if option.option_type != "string":
            raise ManifestError(
                f"ci_env.{option_name} must name a string option "
                f"(got type '{option.option_type}')",
                module_name,
            )
        if not isinstance(placeholder, str) or not placeholder:
            raise ManifestError(
                f"ci_env.{option_name} must be a non-empty string",
                module_name,
            )
        if "\n" in placeholder or "\r" in placeholder:
            raise ManifestError(
                f"ci_env.{option_name} must not contain a newline "
                "(GitHub Actions' environment file reads one NAME=value line "
                "per entry)",
                module_name,
            )
        declarations[option_name] = placeholder

    return declarations


def _parse_throttle_scopes(
    data: dict[str, Any],
    declared_name: str,
    options: Mapping[str, Any],
) -> dict[str, str]:
    """Parse and validate the optional top-level ``throttle_scopes`` section.

    Each entry declares one DRF throttle scope the module's views attach by
    ``throttle_scope``: the key is the scope name — ``quickscale_<module>
    _<purpose>``, Module Conventions rules 2 and 32 — and the value names a
    declared string option whose resolved value is that scope's rate (rule
    1's ``_RATE_LIMIT`` option).  Core resolves the declared rates into the
    module's wiring (``ModuleWiringSpec.throttle_scopes``) and merges them
    when it composes the generated project's ``REST_FRAMEWORK``, so the
    adapter carries no rate map and the option remains the rate's one
    source.

    A scope that does not carry the module stem, or a value that does not
    name a declared string option, fails closed: either would silently
    declare a rate for a scope the module cannot own or a rate with no
    declared source.

    Args:
        data: The full parsed YAML data dictionary.
        declared_name: The manifest's own declared ``name`` (required and
            validated before this section is parsed).  The scope stem is
            checked against it, never against a caller-supplied diagnostic
            label, so a manifest read without one still validates scope
            ownership.
        options: The manifest's declared options (mutable and immutable).

    Returns:
        A dict mapping scope names to option names.  Returns an empty dict
        when the section is absent.

    Raises:
        ManifestError: If the section is not a mapping, a scope name is not
            a ``quickscale_<module>_<purpose>`` name, or a value does not
            name a declared string option.
    """
    raw_section = data.get("throttle_scopes")
    if raw_section is None:
        return {}

    if not isinstance(raw_section, dict):
        raise ManifestError("'throttle_scopes' must be a mapping", declared_name)

    stem = f"quickscale_{declared_name}_"
    declarations: dict[str, str] = {}
    for scope, option_name in raw_section.items():
        if not isinstance(scope, str) or not scope:
            raise ManifestError(
                "'throttle_scopes' keys must be non-empty DRF scope names",
                declared_name,
            )
        if not (scope.startswith(stem) and scope[len(stem) :]):
            raise ManifestError(
                f"throttle_scopes.{scope} must carry the module stem "
                f"('{stem}<purpose>', Module Conventions rules 2 and 32)",
                declared_name,
            )
        if not isinstance(option_name, str) or not option_name:
            raise ManifestError(
                f"throttle_scopes.{scope} must name the option whose "
                "resolved value is the scope's rate",
                declared_name,
            )
        option = options.get(option_name)
        if option is None:
            raise ManifestError(
                f"throttle_scopes.{scope} does not name a declared option",
                declared_name,
            )
        if option.option_type != "string":
            raise ManifestError(
                f"throttle_scopes.{scope} must name a string option "
                f"(got type '{option.option_type}')",
                declared_name,
            )
        declarations[scope] = option_name

    return declarations


#: The keys a top-level ``operations`` section may declare.
_OPERATIONS_SECTION_KEYS = frozenset({"title", "text", "values"})

#: A module-declared operations value name: the ``{name}`` token the text
#: references.  Letters, digits, and underscores only, so the token always
#: forms one unambiguous ``{name}`` marker.
_OPERATIONS_TOKEN_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def _parse_operations(
    data: dict[str, Any],
    module_name: str | None,
    options: Mapping[str, ConfigOption],
) -> ModuleOperations | None:
    """Parse and validate the optional top-level ``operations`` section.

    The section carries the module's operator-facing operations text: a
    ``title`` heading, a Markdown ``text`` body, and the module-owned
    ``values`` the text references as ``{name}`` tokens.  The generated
    project's managed ``quickscale-operations.md`` page renders the section,
    and the user-owned ``OPERATIONS.md`` links that page once instead of
    restating a module value, so the module owns its operations contract.

    A ``text`` token resolves when the page renders: a declared value, a
    declared option's resolved value, or a core contract token (see
    ``quickscale_core.contracts.module_options.ADOPTION_STEP_TOKENS``).  A
    module-declared value whose name shadows a declared option or a core
    token is refused, because it would silently change what the existing
    text means.

    Args:
        data: The full parsed YAML data dictionary.
        module_name: Optional module name for error messages.
        options: The manifest's declared options (mutable and immutable).

    Returns:
        A :class:`ModuleOperations` instance, or ``None`` when the section is
        absent.

    Raises:
        ManifestError: If the section is not a mapping, declares an unknown
            key, leaves ``title`` or ``text`` empty, or declares a value
            whose name is malformed or shadows a reserved token name.
    """
    raw_section = data.get("operations")
    if raw_section is None:
        return None

    if not isinstance(raw_section, dict):
        raise ManifestError("'operations' must be a mapping", module_name)

    # Report the first unknown key in declaration order: heterogeneous keys
    # (a YAML integer against a string) cannot be sorted, and the refusal must
    # stay a ManifestError rather than escape as a bare TypeError.
    unknown_keys = [key for key in raw_section if key not in _OPERATIONS_SECTION_KEYS]
    if unknown_keys:
        allowed = ", ".join(sorted(_OPERATIONS_SECTION_KEYS))
        raise ManifestError(
            f"'operations' declares unknown key '{unknown_keys[0]}' "
            f"(allowed: {allowed})",
            module_name,
        )

    title = raw_section.get("title")
    if not isinstance(title, str) or not title:
        raise ManifestError(
            "'operations.title' must be a non-empty string", module_name
        )

    text = raw_section.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ManifestError("'operations.text' must be a non-empty string", module_name)

    values_raw = raw_section.get("values", {})
    if not isinstance(values_raw, dict):
        raise ManifestError("'operations.values' must be a mapping", module_name)

    reserved = set(options) | set(ADOPTION_STEP_TOKENS)
    values: dict[str, str | tuple[str, ...]] = {}
    for value_name, value in values_raw.items():
        if (
            not isinstance(value_name, str)
            or _OPERATIONS_TOKEN_NAME.match(value_name) is None
        ):
            raise ManifestError(
                "'operations.values' keys must be token names (letters, "
                "digits, and underscores, not starting with a digit)",
                module_name,
            )
        if value_name in reserved:
            raise ManifestError(
                f"'operations.values.{value_name}' would shadow a declared "
                "option or a core contract token; rename the value",
                module_name,
            )
        if isinstance(value, list):
            if not value or not all(isinstance(item, str) and item for item in value):
                raise ManifestError(
                    f"'operations.values.{value_name}' list entries must be "
                    "non-empty strings",
                    module_name,
                )
            values[value_name] = tuple(value)
        elif isinstance(value, str) and value:
            values[value_name] = value
        else:
            raise ManifestError(
                f"'operations.values.{value_name}' must be a non-empty string "
                "or a list of non-empty strings",
                module_name,
            )

    return ModuleOperations(title=title, text=text, values=values)


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
    *,
    require_id: bool = True,
) -> ContractVintage | None:
    """Parse the optional ``contract_vintage`` section from manifest data.

    Returns a :class:`ContractVintage` instance when the section is present,
    or ``None`` when absent.  A present section must declare a non-empty
    ``id``: the id is the step's identity in the one adopted-step namespace
    (Module Manifest Architecture), so an authored vintage without one is
    refused.  ``require_id=False`` is the explicit opt-out for a historical
    embedded copy (a generated project's installed manifest), which may
    predate the id requirement by omitting the key and must stay readable
    for inspection and upgrade; a present ``id`` that is null, empty, or
    not a string is refused either way.

    Args:
        data: The full parsed YAML data dictionary.
        module_name: Optional module name for error messages.
        require_id: When true (the default), refuse a missing ``id``.

    Returns:
        :class:`ContractVintage` or ``None``.

    Raises:
        ManifestError: If the section is malformed, omits ``id`` while one
            is required, or declares a null, non-string, or empty one.
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
    if vintage_id is None and "id" not in raw and not require_id:
        # A historical embedded copy may predate the id requirement by
        # omitting the ``id`` key entirely; a present-but-null ``id`` is
        # malformed, not historical, and falls through to the refusal.
        pass
    elif not isinstance(vintage_id, str) or not vintage_id:
        raise ManifestError(
            "'contract_vintage.id' is required and must be a non-empty string",
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
    """Parse and validate the contract-vintage manual-adoption-steps list.

    A step may reference a core contract value as a declared token (see
    ``quickscale_core.contracts.module_options.ADOPTION_STEP_TOKENS``); the
    value is resolved here, while the manifest is read, so every consumer of
    the parsed steps — status output, apply/update refusals, JSON diagnostics
    — reads the authored constant instead of a hand-synced copy.
    """
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
        steps.append(resolve_adoption_step_tokens(step))
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
