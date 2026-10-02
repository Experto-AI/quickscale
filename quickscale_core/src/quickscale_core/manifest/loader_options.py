"""Config-option parsing for module manifests.

Split out of :mod:`quickscale_core.manifest.loader`; the loader facade
re-exports these helpers so existing imports keep working.  This module owns
config-section parsing and the structural validation of an option's
``validation`` block.
"""

from __future__ import annotations

from collections.abc import Callable
import re
from typing import Any, NoReturn

from quickscale_core.manifest.loader_errors import ManifestError
from quickscale_core.manifest.option_validation import (
    ALLOWED_VALIDATION_KEYS,
    OPTION_TYPE_LABELS,
    option_type_matches,
)
from quickscale_core.manifest.schema import ConfigOption


def _validate_numeric_bound(
    validation: dict[str, Any],
    bound: str,
    option_name: str,
    module_name: str | None,
) -> None:
    """Validate a ``min`` / ``max`` numeric bound in a validation block."""
    value = validation[bound]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManifestError(
            f"Option '{option_name}' validation.{bound} must be a number",
            module_name,
        )


def _validate_condition_key(
    condition_option: Any,
    key_path: str,
    option_name: str,
    module_name: str | None,
) -> None:
    """Reject a condition key that is not a non-empty option name."""
    if not isinstance(condition_option, str) or not condition_option:
        raise ManifestError(
            f"Option '{option_name}' validation.{key_path} keys "
            "must be non-empty option names",
            module_name,
        )


def _raise_condition_error(
    condition_option: Any,
    key_path: str,
    option_name: str,
    module_name: str | None,
    *,
    with_literals: bool,
) -> NoReturn:
    """Raise the shared condition-shape error for one condition value."""
    if with_literals:
        detail = "must be a literal, a non-empty list of literals, or {not_empty: true}"
    else:
        detail = "must be a literal, a non-empty list, or {not_empty: true}"
    raise ManifestError(
        f"Option '{option_name}' validation.{key_path}.{condition_option} {detail}",
        module_name,
    )


def _validate_condition_value(
    condition_option: Any,
    expected: Any,
    key_path: str,
    option_name: str,
    module_name: str | None,
) -> None:
    """Validate one condition entry's value against the shared grammar."""
    if isinstance(expected, list):
        if not expected or not all(
            isinstance(item, (str, int, float, bool)) for item in expected
        ):
            _raise_condition_error(
                condition_option,
                key_path,
                option_name,
                module_name,
                with_literals=True,
            )
    elif isinstance(expected, dict):
        if set(expected) != {"not_empty"} or expected["not_empty"] is not True:
            _raise_condition_error(
                condition_option,
                key_path,
                option_name,
                module_name,
                with_literals=False,
            )
    elif expected is None:
        _raise_condition_error(
            condition_option,
            key_path,
            option_name,
            module_name,
            with_literals=False,
        )
    elif not isinstance(expected, (str, int, float, bool)):
        _raise_condition_error(
            condition_option,
            key_path,
            option_name,
            module_name,
            with_literals=False,
        )


def _validate_condition_mapping(
    condition: dict[str, Any],
    key_path: str,
    option_name: str,
    module_name: str | None,
) -> None:
    """Validate the shared condition grammar of a validation block.

    A condition is a non-empty mapping whose entries must all hold; an entry's
    value is a literal, a non-empty list of literals, or ``{not_empty: true}``.
    """
    if not condition:
        raise ManifestError(
            f"Option '{option_name}' validation.{key_path} must be a "
            "non-empty mapping of another option to its condition",
            module_name,
        )
    for condition_option, expected in condition.items():
        _validate_condition_key(condition_option, key_path, option_name, module_name)
        _validate_condition_value(
            condition_option, expected, key_path, option_name, module_name
        )


def _validate_choices_key(
    validation: dict[str, Any], option_name: str, module_name: str | None
) -> None:
    """Validate a ``choices`` validation key."""
    choices = validation["choices"]
    if not isinstance(choices, list) or not choices:
        raise ManifestError(
            f"Option '{option_name}' validation.choices must be a non-empty list",
            module_name,
        )


def _validate_not_empty_key(
    validation: dict[str, Any], option_name: str, module_name: str | None
) -> None:
    """Validate a ``not_empty`` validation key."""
    if validation["not_empty"] is not True:
        raise ManifestError(
            f"Option '{option_name}' validation.not_empty must be true",
            module_name,
        )


def _validate_min_key(
    validation: dict[str, Any], option_name: str, module_name: str | None
) -> None:
    """Validate a ``min`` validation key."""
    _validate_numeric_bound(validation, "min", option_name, module_name)


def _validate_max_key(
    validation: dict[str, Any], option_name: str, module_name: str | None
) -> None:
    """Validate a ``max`` validation key."""
    _validate_numeric_bound(validation, "max", option_name, module_name)


def _validate_pattern_key(
    validation: dict[str, Any], option_name: str, module_name: str | None
) -> None:
    """Validate a ``pattern`` validation key."""
    pattern = validation["pattern"]
    if not isinstance(pattern, str) or not pattern:
        raise ManifestError(
            f"Option '{option_name}' validation.pattern must be a non-empty string",
            module_name,
        )
    try:
        re.compile(pattern)
    except re.error as error:
        raise ManifestError(
            f"Option '{option_name}' validation.pattern is not a valid "
            f"regular expression: {error}",
            module_name,
        ) from error


def _validate_required_when_key(
    validation: dict[str, Any], option_name: str, module_name: str | None
) -> None:
    """Validate a ``required_when`` validation key."""
    required_when = validation["required_when"]
    if not isinstance(required_when, dict):
        raise ManifestError(
            f"Option '{option_name}' validation.required_when must be a "
            "mapping of another option to its condition",
            module_name,
        )
    _validate_condition_mapping(
        required_when, "required_when", option_name, module_name
    )


def _validate_any_of_key(
    validation: dict[str, Any], option_name: str, module_name: str | None
) -> None:
    """Validate an ``any_of`` validation key."""
    any_of = validation["any_of"]
    if not isinstance(any_of, list) or not any_of:
        raise ManifestError(
            f"Option '{option_name}' validation.any_of must be a non-empty list",
            module_name,
        )
    for entry in any_of:
        if not isinstance(entry, str) or not entry:
            raise ManifestError(
                f"Option '{option_name}' validation.any_of entries must be "
                "non-empty option names",
                module_name,
            )


def _validate_subset_of_key(
    validation: dict[str, Any], option_name: str, module_name: str | None
) -> None:
    """Validate a ``subset_of`` validation key."""
    subset_of = validation["subset_of"]
    if not isinstance(subset_of, str) or not subset_of:
        raise ManifestError(
            f"Option '{option_name}' validation.subset_of must name an option",
            module_name,
        )


def _validate_exclusion_block(
    validation: dict[str, Any],
    key: str,
    option_name: str,
    module_name: str | None,
) -> None:
    """Validate an ``excludes`` / ``intersects`` validation block."""
    block = validation[key]
    if not isinstance(block, dict):
        raise ManifestError(
            f"Option '{option_name}' validation.{key} must be a mapping "
            "with 'values' and an optional 'when'",
            module_name,
        )
    for block_key in block:
        if block_key not in ("values", "when"):
            raise ManifestError(
                f"Option '{option_name}' validation.{key} declares unknown "
                f"key '{block_key}' (allowed: values, when)",
                module_name,
            )
    values = block.get("values")
    if not isinstance(values, list) or not values:
        raise ManifestError(
            f"Option '{option_name}' validation.{key}.values must be a non-empty list",
            module_name,
        )
    if "when" in block:
        when = block["when"]
        if not isinstance(when, dict):
            raise ManifestError(
                f"Option '{option_name}' validation.{key}.when must be a "
                "condition mapping",
                module_name,
            )
        _validate_condition_mapping(when, f"{key}.when", option_name, module_name)


def _validate_excludes_key(
    validation: dict[str, Any], option_name: str, module_name: str | None
) -> None:
    """Validate an ``excludes`` validation key."""
    _validate_exclusion_block(validation, "excludes", option_name, module_name)


def _validate_intersects_key(
    validation: dict[str, Any], option_name: str, module_name: str | None
) -> None:
    """Validate an ``intersects`` validation key."""
    _validate_exclusion_block(validation, "intersects", option_name, module_name)


_VALIDATION_BLOCK_VALIDATORS: dict[
    str, Callable[[dict[str, Any], str, str | None], None]
] = {
    "choices": _validate_choices_key,
    "not_empty": _validate_not_empty_key,
    "min": _validate_min_key,
    "max": _validate_max_key,
    "pattern": _validate_pattern_key,
    "required_when": _validate_required_when_key,
    "any_of": _validate_any_of_key,
    "subset_of": _validate_subset_of_key,
    "excludes": _validate_excludes_key,
    "intersects": _validate_intersects_key,
}


def _validate_validation_block(
    validation: dict[str, Any], option_name: str, module_name: str | None
) -> None:
    """Validate the shape of one option's ``validation`` block.

    The block may be empty, but every key it does carry must be one the
    option-validation engine understands, with a shape that engine can apply.
    Structural errors fail the load so an unread declaration cannot ship.
    """
    for key in validation:
        if key not in ALLOWED_VALIDATION_KEYS:
            allowed = ", ".join(sorted(ALLOWED_VALIDATION_KEYS))
            raise ManifestError(
                f"Option '{option_name}' validation declares unknown key "
                f"'{key}' (allowed: {allowed})",
                module_name,
            )

    for key, validator in _VALIDATION_BLOCK_VALIDATORS.items():
        if key in validation:
            validator(validation, option_name, module_name)


def _condition_references(condition: Any) -> list[str]:
    """Return the option names a condition mapping references."""
    if not isinstance(condition, dict):
        return []
    return [key for key in condition if isinstance(key, str)]


def _collect_option_references(option: ConfigOption) -> list[str]:
    """Return every option name one option's validation block references."""
    validation = option.validation or {}
    references: list[str] = []
    references.extend(_condition_references(validation.get("required_when")))
    any_of = validation.get("any_of")
    if isinstance(any_of, list):
        references.extend(entry for entry in any_of if isinstance(entry, str))
    subset_of = validation.get("subset_of")
    if isinstance(subset_of, str):
        references.append(subset_of)
    for key in ("excludes", "intersects"):
        block = validation.get(key)
        if isinstance(block, dict):
            references.extend(_condition_references(block.get("when")))
    return references


def _validate_option_references(
    mutable_options: dict[str, ConfigOption],
    immutable_options: dict[str, ConfigOption],
    module_name: str | None,
) -> None:
    """Reject validation blocks that reference an undeclared option."""
    declared = set(mutable_options) | set(immutable_options)
    for section in (mutable_options, immutable_options):
        for option_name, option in section.items():
            for reference in _collect_option_references(option):
                if reference not in declared:
                    raise ManifestError(
                        f"Option '{option_name}' validation references unknown "
                        f"option '{reference}'",
                        module_name,
                    )


def _parse_config_option(
    name: str, data: dict[str, Any], mutability: str, module_name: str | None
) -> ConfigOption:
    """Parse a single config option from manifest data"""
    option_type = data.get("type")
    if not isinstance(option_type, str) or not option_type:
        raise ManifestError(
            f"Option '{name}' must declare a non-empty 'type'",
            module_name,
        )
    if option_type not in OPTION_TYPE_LABELS:
        allowed = ", ".join(sorted(OPTION_TYPE_LABELS))
        raise ManifestError(
            f"Option '{name}' declares unsupported type '{option_type}' "
            f"(allowed: {allowed})",
            module_name,
        )

    description = data.get("description")
    if not isinstance(description, str) or not description:
        raise ManifestError(
            f"Option '{name}' must declare a non-empty 'description'",
            module_name,
        )

    validation = data.get("validation")
    if not isinstance(validation, dict):
        raise ManifestError(
            f"Option '{name}' must declare a 'validation' mapping "
            "(use '{}' when the option has no constraint)",
            module_name,
        )
    _validate_validation_block(validation, name, module_name)

    if "default" not in data:
        raise ManifestError(
            f"Option '{name}' must declare a 'default'",
            module_name,
        )
    default = data["default"]
    if default is None:
        raise ManifestError(
            f"Option '{name}' 'default' must not be null",
            module_name,
        )
    if not option_type_matches(option_type, default):
        raise ManifestError(
            f"Option '{name}' 'default' must match its declared type '{option_type}'",
            module_name,
        )

    return ConfigOption(
        name=name,
        option_type=option_type,
        default=default,
        django_setting=data.get("django_setting"),
        description=description,
        mutability=mutability,  # type: ignore[arg-type]
        validation=dict(validation),
    )


def _parse_config_section(
    config_data: dict[str, Any], section: str, module_name: str | None
) -> dict[str, ConfigOption]:
    """Parse a config section (mutable or immutable)"""
    options = {}
    section_data = config_data.get(section, {})

    if not isinstance(section_data, dict):
        raise ManifestError(f"config.{section} must be a mapping", module_name)

    for option_name, option_data in section_data.items():
        if option_data is None:
            option_data = {}
        elif not isinstance(option_data, dict):
            raise ManifestError(
                f"config.{section}.{option_name} must be a mapping or empty",
                module_name,
            )

        options[option_name] = _parse_config_option(
            option_name, option_data, section, module_name
        )

    return options


def _validate_mutable_options(
    mutable_options: dict[str, ConfigOption], module_name: str | None
) -> None:
    """Validate that mutable options have django_setting defined"""
    for opt_name, option in mutable_options.items():
        if not option.django_setting:
            raise ManifestError(
                f"Mutable option '{opt_name}' must have 'django_setting' defined",
                module_name,
            )


def _parse_retired_options(
    data: dict[str, Any],
    mutable_options: dict[str, ConfigOption],
    immutable_options: dict[str, ConfigOption],
    module_name: str | None,
) -> dict[str, str]:
    """Parse and validate the optional top-level ``retired_options`` section.

    Each entry maps a retired option key to the message that names its
    removal.  A key that is still a declared option is rejected: a key is
    either live or retired, never both.

    Args:
        data: The full parsed YAML data dictionary.
        mutable_options: Declared mutable options (collision check).
        immutable_options: Declared immutable options (collision check).
        module_name: Optional module name for error messages.

    Returns:
        A mapping of retired option names to their removal messages.  Empty
        when the section is absent.

    Raises:
        ManifestError: If the section is malformed or names a declared option.
    """
    raw_section = data.get("retired_options")
    if raw_section is None:
        return {}

    if not isinstance(raw_section, dict):
        raise ManifestError("'retired_options' must be a mapping", module_name)

    declared = set(mutable_options) | set(immutable_options)
    retired: dict[str, str] = {}
    for key, message in raw_section.items():
        if not isinstance(key, str) or not key:
            raise ManifestError(
                "'retired_options' keys must be non-empty option names",
                module_name,
            )
        if not isinstance(message, str) or not message:
            raise ManifestError(
                f"'retired_options.{key}' must be a non-empty removal message",
                module_name,
            )
        if key in declared:
            raise ManifestError(
                f"'retired_options.{key}' is also a declared option",
                module_name,
            )
        retired[key] = message
    return retired
