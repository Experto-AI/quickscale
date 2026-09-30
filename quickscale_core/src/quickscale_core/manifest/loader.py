"""Module Manifest Loader

Loads and validates module.yml manifest files.
Supports optional ``derivation`` section for T2.3+ derivation/validation rules.
"""

from __future__ import annotations

import posixpath
from pathlib import Path
import re
import string
from typing import Any

import yaml

from quickscale_core import __version__ as _core_version
from quickscale_core.manifest.derivation import NORMALIZATION_RULE_KINDS
from quickscale_core.manifest.option_validation import (
    ALLOWED_VALIDATION_KEYS,
    OPTION_TYPE_LABELS,
    option_type_matches,
)
from quickscale_core.manifest.schema import (
    MANAGED_FILE_ROOT_PREFIX,
    ConfigOption,
    ContractVintage,
    ImpliesEntry,
    ManagedFileDeclaration,
    ModuleManifest,
    ProjectContractStep,
    ProjectContractVintage,
)

#: Packaged generated-project contract declaration (SA207).
PROJECT_CONTRACT_DECLARATION_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "project_contract.yml"
)


class ManifestError(Exception):
    """Error loading or validating a module manifest"""

    def __init__(self, message: str, module_name: str | None = None):
        self.message = message
        self.module_name = module_name
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with module name"""
        if self.module_name:
            return f"[{self.module_name}] {self.message}"
        return self.message


class ModuleVersionMismatchError(RuntimeError):
    """Raised when an embedded module's manifest version predates the current
    core version, indicating the module content is too old to wire safely.

    This error is intentionally a plain ``RuntimeError`` subclass — **not**
    ``ManifestError`` — so that callers can catch it independently from
    structural manifest loading/validation errors.  The stable message
    format is::

        Module '{module_name}' version mismatch: found {found};
        expected core version {core_version}.
    """


def _parse_canonical_version_triple(version_str: str) -> tuple[int, int, int]:
    """Parse a dotted decimal version string into a (major, minor, patch) triple.

    Enforces lockstep canonical form: exactly three dot-separated ASCII
    decimal (U+0030-U+0039) components, each parsed as int, then
    reserialized as ``major.minor.patch``.  Raises :exc:`ValueError` if
    any component is empty, contains non-digit characters (including signs
    or Unicode digits), or the raw input differs from canonical
    reserialization.

    This is a private lockstep-only parser — **never** call shared
    normalizers, ``str.strip()``, or import ``packaging``.
    """
    parts = version_str.split(".")
    if len(parts) != 3:
        raise ValueError(
            f"Version must have exactly 3 dot-separated components, got {len(parts)}"
        )
    # Reject non-ASCII-digit or empty components BEFORE int() so that
    # signed (+1), Unicode-digit (١), and whitespace-padded (" 1") inputs
    # fail the explicit ASCII 0-9 check rather than relying on int()'s
    # implicit stripping and sign handling.
    for i, part in enumerate(parts):
        if not part:
            raise ValueError(f"Version component {i} is empty")
        if not part.isascii() or not part.isdigit():
            raise ValueError(
                f"Version component {i} must be ASCII decimal digits "
                f"(0-9), got {part!r}"
            )
    try:
        major, minor, patch = (int(p) for p in parts)
    except ValueError:
        raise ValueError("Version components must be decimal integers")
    canonical = f"{major}.{minor}.{patch}"
    if version_str != canonical:
        raise ValueError(
            f"Version must be canonical three-component dotted decimal "
            f"(got {version_str!r}, expected {canonical!r})"
        )
    return (major, minor, patch)


def assert_manifest_version_matches_core(
    manifest_version: str,
    module_name: str,
) -> None:
    """Assert that *manifest_version* matches the current core version
    (:data:`quickscale_core.__version__`) as a lockstep canonical version
    triple.

    Lockstep canonical equality is enforced — the version string must be a
    canonical three-component dotted decimal (``major.minor.patch``):
    * Empty, whitespace-only, or non-string manifest versions are rejected.
    * Unparseable manifest versions (e.g. ``"abc"``) are rejected.
    * A single-component version (e.g. ``"0"``) is rejected.
    * A version that differs from the core version — including alpha,
      pre-release suffixes (e.g. ``"0.87.0-alpha"``), older, or **newer**
      — is rejected.
    * Non-canonical spellings — leading-zero components (``"0.87.00"``),
      whitespace padding (``" 0.87.0 "``), extra components (``"0.87.0.1"``)
      — are rejected **before** triple comparison.
    * Signed (``"+1.2.3"``, ``"-1.2.3"``), Unicode-digit (``"١.2.3"``),
      and empty-component (``"0..0"``) inputs are rejected by the explicit
      ASCII ``0-9`` check **before** ``int()`` parsing.

    Args:
        manifest_version: Version string from a module manifest (e.g.
            ``"0.87.0"``).
        module_name: Module name for error messages.

    Raises:
        ModuleVersionMismatchError: If *manifest_version* does not match
            the current core version as a canonical version triple.
    """
    if (
        not isinstance(manifest_version, str)
        or not manifest_version
        or manifest_version.isspace()
    ):
        raise ModuleVersionMismatchError(
            f"Module '{module_name}' version mismatch: "
            f"found {manifest_version!r}; expected core version "
            f"{_core_version}.",
        )

    # Lockstep canonical version parsing: both the manifest version and
    # the core version are independently parsed into (major, minor, patch)
    # triples.  A manifest version that is not already in canonical form
    # (exactly three dot-separated decimal components) is rejected before
    # any comparison.
    try:
        manifest_triple = _parse_canonical_version_triple(manifest_version)
        core_triple = _parse_canonical_version_triple(_core_version)
    except ValueError:
        raise ModuleVersionMismatchError(
            f"Module '{module_name}' version mismatch: "
            f"found {manifest_version}; expected core version "
            f"{_core_version}.",
        )

    if manifest_triple != core_triple:
        raise ModuleVersionMismatchError(
            f"Module '{module_name}' version mismatch: "
            f"found {manifest_version}; expected core version "
            f"{_core_version}.",
        )


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
        if not isinstance(condition_option, str) or not condition_option:
            raise ManifestError(
                f"Option '{option_name}' validation.{key_path} keys "
                "must be non-empty option names",
                module_name,
            )
        if isinstance(expected, list):
            if not expected or not all(
                isinstance(item, (str, int, float, bool)) for item in expected
            ):
                raise ManifestError(
                    f"Option '{option_name}' validation.{key_path}."
                    f"{condition_option} must be a literal, a non-empty list of "
                    "literals, or {not_empty: true}",
                    module_name,
                )
        elif isinstance(expected, dict):
            if set(expected) != {"not_empty"} or expected["not_empty"] is not True:
                raise ManifestError(
                    f"Option '{option_name}' validation.{key_path}."
                    f"{condition_option} must be a literal, a non-empty list, "
                    "or {not_empty: true}",
                    module_name,
                )
        elif expected is None:
            raise ManifestError(
                f"Option '{option_name}' validation.{key_path}."
                f"{condition_option} must be a literal, a non-empty list, "
                "or {not_empty: true}",
                module_name,
            )
        elif not isinstance(expected, (str, int, float, bool)):
            raise ManifestError(
                f"Option '{option_name}' validation.{key_path}."
                f"{condition_option} must be a literal, a non-empty list, "
                "or {not_empty: true}",
                module_name,
            )


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

    if "choices" in validation:
        choices = validation["choices"]
        if not isinstance(choices, list) or not choices:
            raise ManifestError(
                f"Option '{option_name}' validation.choices must be a non-empty list",
                module_name,
            )

    if "not_empty" in validation:
        if validation["not_empty"] is not True:
            raise ManifestError(
                f"Option '{option_name}' validation.not_empty must be true",
                module_name,
            )

    if "min" in validation:
        _validate_numeric_bound(validation, "min", option_name, module_name)
    if "max" in validation:
        _validate_numeric_bound(validation, "max", option_name, module_name)

    if "pattern" in validation:
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

    if "required_when" in validation:
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

    if "any_of" in validation:
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

    if "subset_of" in validation:
        subset_of = validation["subset_of"]
        if not isinstance(subset_of, str) or not subset_of:
            raise ManifestError(
                f"Option '{option_name}' validation.subset_of must name an option",
                module_name,
            )

    for key in ("excludes", "intersects"):
        if key not in validation:
            continue
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
                f"Option '{option_name}' validation.{key}.values must be a "
                "non-empty list",
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


def _condition_references(condition: Any) -> list[str]:
    """Return the option names a condition mapping references."""
    if not isinstance(condition, dict):
        return []
    return [key for key in condition if isinstance(key, str)]


def _validate_option_references(
    mutable_options: dict[str, ConfigOption],
    immutable_options: dict[str, ConfigOption],
    module_name: str | None,
) -> None:
    """Reject validation blocks that reference an undeclared option."""
    declared = set(mutable_options) | set(immutable_options)
    for section in (mutable_options, immutable_options):
        for option_name, option in section.items():
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
            for reference in references:
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


def _parse_yaml_content(yaml_content: str, module_name: str | None) -> dict[str, Any]:
    """Parse YAML content and return data dictionary"""
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise ManifestError(f"Invalid YAML syntax: {e}", module_name) from e

    if not isinstance(data, dict):
        raise ManifestError("Manifest must be a YAML mapping", module_name)

    return data


def _validate_required_string_field(
    data: dict[str, Any], field: str, module_name: str | None
) -> str:
    """Validate a required string field exists and is non-empty"""
    if field not in data:
        raise ManifestError(f"Missing required field '{field}'", module_name)

    value = data[field]
    if not isinstance(value, str) or not value:
        raise ManifestError(f"'{field}' must be a non-empty string", module_name)

    return value


def _validate_list_field(
    data: dict[str, Any], field: str, module_name: str | None
) -> list[str]:
    """Validate an optional list field"""
    value = data.get(field, [])
    if not isinstance(value, list):
        raise ManifestError(f"'{field}' must be a list", module_name)
    return value


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

        declarations[key] = ManagedFileDeclaration(
            key=key,
            renderer=renderer,
            output_path=output_path,
        )

    return declarations


# ---------------------------------------------------------------------------
# Derivation section parsing (T2.3+)
# ---------------------------------------------------------------------------

#: Parameter keys every normalization rule may carry, whatever its kind.
_NORMALIZATION_RULE_COMMON_KEYS = frozenset(
    {"rule_type", "source_key", "target_key", "description"}
)
#: Kind-specific parameter keys; a kind absent here takes no other parameter.
_NORMALIZATION_RULE_KIND_KEYS: dict[str, frozenset[str]] = {
    "choice_map": frozenset({"mapping"}),
    "slug": frozenset({"max_length", "replace"}),
    "list": frozenset({"item_rules"}),
}

_DERIVATION_LIST_FIELDS = frozenset(
    {
        "normalization_rules",
        "validation_rules",
        "legacy_aliases",
        "derived_settings",
        "wiring_projections",
    }
)

#: Per-option derivation sub-sections the engine executes.  Anything else is
#: refused at load, so a misspelled declaration cannot load and be ignored.
_OPTION_DERIVATION_KEYS = frozenset(
    {"normalization_rules", "derived_settings", "wiring_projections"}
)

#: Top-level derivation sections the parser accepts; anything else is refused.
_DERIVATION_SECTION_KEYS = frozenset(
    {
        "normalization_rules",
        "validation_rules",
        "legacy_aliases",
        "derived_settings",
        "wiring_projections",
        "option_derivations",
    }
)

#: Executable wiring fields and derivation types a projection may declare.
_WIRING_FIELDS = frozenset(
    {"apps", "middleware", "url_includes", "pre_home_url_includes"}
)
_DERIVATION_TYPES = frozenset({"static", "direct", "conditional", "computed"})

#: Top-level derivation sections nothing executes.  A non-null declaration is
#: refused at load so a rule or alias that would silently do nothing fails hard
#: instead of shipping.
_INERT_DERIVATION_SECTION_ERRORS = {
    "normalization_rules": (
        "derivation.normalization_rules is no longer executed; declare the rule "
        "under derivation.option_derivations.<option>.normalization_rules"
    ),
    "validation_rules": (
        "derivation.validation_rules is no longer executed; declare the option's "
        "checks in its config validation block"
    ),
    "legacy_aliases": (
        "derivation.legacy_aliases is no longer executed; a renamed option is "
        "refused by name through the manifest's retired_options block"
    ),
}


def _assert_is_mapping(
    value: Any,
    path: str,
    module_name: str | None,
) -> dict[str, Any]:
    """Assert *value* is a mapping and return it; raise otherwise."""
    if not isinstance(value, dict):
        raise ManifestError(f"'{path}' must be a mapping", module_name)
    return value


def _assert_is_list(
    value: Any,
    path: str,
    module_name: str | None,
) -> list[Any]:
    """Assert *value* is a list and return it; raise otherwise."""
    if not isinstance(value, list):
        raise ManifestError(f"'{path}' must be a list", module_name)
    return value


def _validate_normalization_rule_list(
    rules: Any,
    path: str,
    module_name: str | None,
) -> None:
    """Validate the shape of a declared normalization-rule list.

    Structural errors fail the load so a rule parameter the resolver would
    silently ignore (a non-integer ``slug.max_length``) cannot ship.
    """
    if not isinstance(rules, list):
        raise ManifestError(f"'{path}' must be a list", module_name)
    for index, rule in enumerate(rules):
        rule_path = f"{path}[{index}]"
        if not isinstance(rule, dict):
            raise ManifestError(f"'{rule_path}' must be a mapping", module_name)
        rule_type = rule.get("rule_type")
        if not isinstance(rule_type, str) or not rule_type:
            raise ManifestError(
                f"'{rule_path}.rule_type' must be a non-empty string",
                module_name,
            )
        if rule_type not in NORMALIZATION_RULE_KINDS:
            allowed = ", ".join(sorted(NORMALIZATION_RULE_KINDS))
            raise ManifestError(
                f"'{rule_path}.rule_type' must be one of: {allowed}",
                module_name,
            )
        allowed_keys = (
            _NORMALIZATION_RULE_COMMON_KEYS
            | _NORMALIZATION_RULE_KIND_KEYS.get(rule_type, frozenset())
        )
        for parameter in rule:
            if parameter not in allowed_keys:
                raise ManifestError(
                    f"'{rule_path}.{parameter}' is not a supported parameter "
                    f"for rule_type '{rule_type}'",
                    module_name,
                )
        if "max_length" in rule:
            max_length = rule["max_length"]
            if (
                isinstance(max_length, bool)
                or not isinstance(max_length, int)
                or max_length < 1
            ):
                raise ManifestError(
                    f"'{rule_path}.max_length' must be a positive integer",
                    module_name,
                )
        if "replace" in rule:
            replace = rule["replace"]
            if not isinstance(replace, dict) or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in replace.items()
            ):
                raise ManifestError(
                    f"'{rule_path}.replace' must be a mapping of strings",
                    module_name,
                )
        if "mapping" in rule:
            mapping = rule["mapping"]
            if not isinstance(mapping, dict) or any(
                not isinstance(key, str) for key in mapping
            ):
                raise ManifestError(
                    f"'{rule_path}.mapping' must be a mapping keyed by strings",
                    module_name,
                )
        if "item_rules" in rule:
            _validate_normalization_rule_list(
                rule["item_rules"], f"{rule_path}.item_rules", module_name
            )


def _selector_chain_yields_unhashable(
    selector: str, option_derivations: dict[str, Any]
) -> bool:
    """Return whether *selector*'s declared normalization can yield a container.

    A conditional branch selector is used as a mapping key, so its normalized
    value must stay scalar; a ``list`` rule or a ``choice_map`` value that is a
    container would make branch membership crash.
    """
    rules = option_derivations.get(selector, {}).get("normalization_rules", [])
    if not isinstance(rules, list):
        # A malformed rule list is refused by the normalization-rule validation.
        return False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if rule.get("rule_type") == "list":
            return True
        if rule.get("rule_type") == "choice_map":
            mapping = rule.get("mapping")
            if isinstance(mapping, dict) and any(
                not isinstance(value, (str, int, float, bool, type(None)))
                for value in mapping.values()
            ):
                return True
    return False


def _validate_rule_owner_keys(
    rule: dict[str, Any],
    opt_key: str,
    path: str,
    module_name: str | None,
    *,
    require_present: bool,
) -> None:
    """Require a per-option rule's declared key names to match its option.

    An outer rule must name the owning option; nested item rules are executed
    per item and may omit the names, but a name they do declare must match.
    """
    source_key = rule.get("source_key")
    target_key = rule.get("target_key")
    if require_present:
        if source_key != opt_key or target_key != opt_key:
            raise ManifestError(
                f"{path} must declare source_key and target_key as '{opt_key}'",
                module_name,
            )
    else:
        if "source_key" in rule and rule["source_key"] != opt_key:
            raise ManifestError(
                f"{path} must declare source_key as '{opt_key}'", module_name
            )
        if "target_key" in rule and rule["target_key"] != opt_key:
            raise ManifestError(
                f"{path} must declare target_key as '{opt_key}'", module_name
            )
    for index, nested in enumerate(rule.get("item_rules") or []):
        if isinstance(nested, dict):
            _validate_rule_owner_keys(
                nested,
                opt_key,
                f"{path}.item_rules[{index}]",
                module_name,
                require_present=False,
            )


def _validate_wiring_contribution(
    value: Any, wiring_field: str, path: str, module_name: str | None
) -> None:
    """Validate a concrete projection contribution for its wiring field.

    The resolver discards a non-list contribution and any item that is not a
    ``[route, include]`` pair for URL fields; a declaration that would be
    discarded must fail the load instead of silently contributing nothing.
    """
    if not isinstance(value, (list, tuple)):
        raise ManifestError(
            f"{path} must be a list of contributions for '{wiring_field}'",
            module_name,
        )
    if wiring_field in ("url_includes", "pre_home_url_includes"):
        for index, item in enumerate(value):
            if (
                not isinstance(item, (list, tuple))
                or len(item) != 2
                or not all(isinstance(part, str) for part in item)
            ):
                raise ManifestError(
                    f"{path}[{index}] must be a [route, include] pair of strings",
                    module_name,
                )
    else:
        for index, item in enumerate(value):
            if not isinstance(item, str):
                raise ManifestError(
                    f"{path}[{index}] must be an app or middleware label",
                    module_name,
                )


def _validate_computed_template(
    template: str,
    field_path: str,
    module_name: str | None,
    declared_options: dict[str, Any],
) -> None:
    """Refuse a computed template the resolver cannot render safely.

    Only plain ``{option_name}`` placeholders are supported; attribute or item
    access and nested format specs would raise outside the resolver's handled
    exceptions, and an empty template cannot be executed.
    """
    if not template:
        raise ManifestError(f"{field_path} must be a non-empty template", module_name)
    try:
        fields = list(string.Formatter().parse(template))
    except ValueError as error:
        raise ManifestError(
            f"{field_path} is not a valid format string: {error}", module_name
        ) from error
    for _literal, field_name, format_spec, conversion in fields:
        if field_name is None:
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field_name):
            raise ManifestError(
                f"{field_path} placeholder '{field_name}' must be a plain option name",
                module_name,
            )
        if field_name not in declared_options:
            raise ManifestError(
                f"{field_path} references unknown option '{field_name}'",
                module_name,
            )
        if conversion is not None and conversion not in ("s", "r", "a"):
            raise ManifestError(
                f"{field_path} conversion '!{conversion}' is not supported",
                module_name,
            )
        if "{" in (format_spec or ""):
            raise ManifestError(
                f"{field_path} format spec may not nest placeholders",
                module_name,
            )
        if format_spec:
            try:
                format("x", format_spec)
            except ValueError, TypeError:
                raise ManifestError(
                    f"{field_path} format spec '{format_spec}' cannot format a string",
                    module_name,
                ) from None


def _validate_derivation_entry(
    entry: dict[str, Any],
    path: str,
    module_name: str | None,
    *,
    wiring: bool,
    declared_options: dict[str, Any],
    option_derivations: dict[str, Any],
) -> None:
    """Validate the shapes a derivation entry's parser and resolver consume.

    ``expression`` is parsed as a mapping, ``source_options`` as a list of
    option names, and wiring ``default`` as a list; projection fields and
    derivation types must be executable values; a conditional selector must
    name a declared option whose normalization stays scalar.  Anything consumed
    and malformed fails the load here so an accepted declaration can never
    crash schema construction or resolution or silently contribute nothing.
    """
    derivation_type = str(
        entry.get("derivation_type", "static" if wiring else "direct")
    )
    if derivation_type not in _DERIVATION_TYPES:
        allowed = ", ".join(sorted(_DERIVATION_TYPES))
        raise ManifestError(
            f"{path}.derivation_type must be one of: {allowed}", module_name
        )
    if wiring:
        wiring_field_raw = entry.get("wiring_field")
        if (
            not isinstance(wiring_field_raw, str)
            or wiring_field_raw not in _WIRING_FIELDS
        ):
            allowed = ", ".join(sorted(_WIRING_FIELDS))
            raise ManifestError(
                f"{path}.wiring_field must be one of: {allowed}", module_name
            )
        wiring_field = wiring_field_raw
        if "default" in entry:
            _validate_wiring_contribution(
                entry["default"], wiring_field, f"{path}.default", module_name
            )
    if "expression" in entry:
        expression = entry["expression"]
        if not isinstance(expression, dict):
            raise ManifestError(f"{path}.expression must be a mapping", module_name)
        if (
            derivation_type == "conditional"
            and "branches" in expression
            and not isinstance(expression["branches"], dict)
        ):
            raise ManifestError(
                f"{path}.expression.branches must be a mapping", module_name
            )
        if derivation_type == "computed":
            if wiring:
                if "values" in expression:
                    values = expression["values"]
                    if not isinstance(values, list) or not values:
                        raise ManifestError(
                            f"{path}.expression.values must be a non-empty list",
                            module_name,
                        )
                    for index, value in enumerate(values):
                        if not isinstance(value, str):
                            raise ManifestError(
                                f"{path}.expression.values[{index}] must be a string",
                                module_name,
                            )
                        _validate_computed_template(
                            value,
                            f"{path}.expression.values[{index}]",
                            module_name,
                            declared_options,
                        )
            elif "template" in expression:
                template = expression["template"]
                if not isinstance(template, str):
                    raise ManifestError(
                        f"{path}.expression.template must be a string", module_name
                    )
                _validate_computed_template(
                    template,
                    f"{path}.expression.template",
                    module_name,
                    declared_options,
                )
        if derivation_type == "static" and wiring and "value" in expression:
            _validate_wiring_contribution(
                expression["value"],
                wiring_field,
                f"{path}.expression.value",
                module_name,
            )
        if derivation_type == "conditional" and wiring:
            branches = expression.get("branches")
            if isinstance(branches, dict):
                for branch_key, branch_value in branches.items():
                    _validate_wiring_contribution(
                        branch_value,
                        wiring_field,
                        f"{path}.expression.branches.{branch_key}",
                        module_name,
                    )
        if (
            derivation_type == "computed"
            and wiring
            and wiring_field in ("url_includes", "pre_home_url_includes")
        ):
            raise ManifestError(
                f"{path}: computed projections cannot target URL wiring fields",
                module_name,
            )
        allowed_expression_keys = {
            "direct": {"option"},
            "static": {"value"},
            "conditional": {"branches"},
            "computed": {"values"} if wiring else {"template"},
        }[derivation_type]
        for expression_key in expression:
            if expression_key not in allowed_expression_keys:
                allowed = ", ".join(sorted(allowed_expression_keys))
                raise ManifestError(
                    f"{path}.expression declares unknown key '{expression_key}' "
                    f"(allowed: {allowed})",
                    module_name,
                )
    if derivation_type == "direct":
        expression = entry.get("expression")
        if not isinstance(expression, dict):
            raise ManifestError(
                f"{path}.expression must be a mapping with an 'option' for a "
                "direct projection",
                module_name,
            )
        option_key = expression.get("option")
        if not isinstance(option_key, str) or not option_key:
            raise ManifestError(
                f"{path}.expression.option must be a declared option name",
                module_name,
            )
        declared = declared_options.get(option_key)
        if declared is None:
            raise ManifestError(
                f"{path}.expression.option references unknown option '{option_key}'",
                module_name,
            )
        if (
            wiring
            and wiring_field in ("url_includes", "pre_home_url_includes")
            and getattr(declared, "option_type", None) != "list"
        ):
            raise ManifestError(
                f"{path}.expression.option must be a list option to target "
                f"'{wiring_field}'",
                module_name,
            )
        if wiring and wiring_field in ("url_includes", "pre_home_url_includes"):
            default_items = getattr(declared, "default", None)
            if isinstance(default_items, (list, tuple)) and default_items:
                _validate_wiring_contribution(
                    default_items,
                    wiring_field,
                    f"{path}.expression.option default",
                    module_name,
                )
    if derivation_type != "direct":
        expression = entry.get("expression")
        if not isinstance(expression, dict):
            raise ManifestError(f"{path}.expression must be a mapping", module_name)
        required_key = {
            "static": "value",
            "conditional": "branches",
            "computed": "values" if wiring else "template",
        }.get(derivation_type)
        if required_key is not None and required_key not in expression:
            raise ManifestError(
                f"{path}.expression.{required_key} is required for a "
                f"{derivation_type} projection",
                module_name,
            )
    if derivation_type == "conditional":
        selectors = entry.get("source_options")
        if not isinstance(selectors, list) or not selectors:
            raise ManifestError(
                f"{path}.source_options must list the selector option for a "
                "conditional projection",
                module_name,
            )
    if not wiring:
        setting_key = entry.get("setting_key")
        if not isinstance(setting_key, str) or not setting_key:
            raise ManifestError(
                f"{path}.setting_key must be a non-empty string", module_name
            )
    if "source_options" in entry and derivation_type != "conditional":
        raise ManifestError(
            f"{path}.source_options is only valid for a conditional projection",
            module_name,
        )
    if "source_options" in entry:
        source_options = entry["source_options"]
        if not isinstance(source_options, list):
            raise ManifestError(f"{path}.source_options must be a list", module_name)
        for index, item in enumerate(source_options):
            if not isinstance(item, str):
                raise ManifestError(
                    f"{path}.source_options[{index}] must be an option name",
                    module_name,
                )
        if derivation_type == "conditional":
            for item in source_options:
                declared = declared_options.get(item)
                if declared is None:
                    raise ManifestError(
                        f"{path}.source_options references unknown option '{item}'",
                        module_name,
                    )
                if getattr(declared, "option_type", None) == "list":
                    raise ManifestError(
                        f"{path}.source_options cannot select list option '{item}'",
                        module_name,
                    )
                if _selector_chain_yields_unhashable(item, option_derivations):
                    raise ManifestError(
                        f"{path}.source_options cannot select '{item}': its "
                        "normalization can produce a non-scalar value",
                        module_name,
                    )


def _parse_derivation_section(
    data: dict[str, Any],
    module_name: str | None,
    declared_options: dict[str, Any],
) -> dict[str, Any]:
    """Parse the optional ``derivation`` section from manifest data.

    Returns a dict with keys matching ``ModuleManifest`` derivation fields:
    ``derivation_rules``, ``validation_rules``, ``legacy_aliases``,
    ``derived_settings``, ``wiring_projections``, and ``option_derivations``.
    List fields default to empty lists; ``option_derivations`` defaults to
    an empty dict.  The legacy top-level ``normalization_rules``,
    ``validation_rules``, and ``legacy_aliases`` sections are refused: nothing
    in the live engine executes them, so accepting one would ship an unread
    declaration.

    Args:
        data: The full parsed YAML data dictionary.
        module_name: Optional module name for error messages.

    Returns:
        Dict of parsed derivation sub-sections.

    Raises:
        ManifestError: If a section is malformed or an inert legacy section is
            declared.
    """
    raw = data.get("derivation")
    if raw is None:
        result: dict[str, Any] = {field: [] for field in _DERIVATION_LIST_FIELDS}
        result["option_derivations"] = {}
        return result

    derivation = _assert_is_mapping(raw, "derivation", module_name)
    for inert_field, inert_message in _INERT_DERIVATION_SECTION_ERRORS.items():
        if inert_field in derivation:
            raise ManifestError(inert_message, module_name)
    for key in derivation:
        if key not in _DERIVATION_SECTION_KEYS:
            allowed = ", ".join(sorted(_DERIVATION_SECTION_KEYS))
            raise ManifestError(
                f"derivation declares unknown key '{key}' (allowed: {allowed})",
                module_name,
            )

    result = {}
    for field in _DERIVATION_LIST_FIELDS:
        section = derivation.get(field, [])
        if section is None:
            result[field] = []
            continue
        result[field] = _assert_is_list(
            section,
            f"derivation.{field}",
            module_name,
        )

    # Parse per-option derivations (a mapping of option_key -> raw dict).
    opt_raw = derivation.get("option_derivations", {})
    if opt_raw is None:
        result["option_derivations"] = {}
    elif isinstance(opt_raw, dict):
        result["option_derivations"] = {}
        for opt_key, opt_value in opt_raw.items():
            if opt_value is None:
                result["option_derivations"][opt_key] = {}
            elif isinstance(opt_value, dict):
                result["option_derivations"][opt_key] = opt_value
            else:
                raise ManifestError(
                    f"derivation.option_derivations.{opt_key} must be a mapping",
                    module_name,
                )
    else:
        raise ManifestError(
            "derivation.option_derivations must be a mapping",
            module_name,
        )

    for field in ("derived_settings", "wiring_projections"):
        for index, entry in enumerate(result[field]):
            if not isinstance(entry, dict):
                raise ManifestError(
                    f"derivation.{field}[{index}] must be a mapping",
                    module_name,
                )
            _validate_derivation_entry(
                entry,
                f"derivation.{field}[{index}]",
                module_name,
                wiring=field == "wiring_projections",
                declared_options=declared_options,
                option_derivations=result["option_derivations"],
            )

    for opt_key, opt_value in result["option_derivations"].items():
        if "validation_rules" in opt_value:
            raise ManifestError(
                f"derivation.option_derivations.{opt_key}.validation_rules is no "
                "longer executed; declare the option's checks in its config "
                "validation block",
                module_name,
            )
        if "legacy_aliases" in opt_value:
            raise ManifestError(
                f"derivation.option_derivations.{opt_key}.legacy_aliases is no "
                "longer executed; a renamed option is refused by name through "
                "the manifest's retired_options block",
                module_name,
            )
        for key in opt_value:
            if not isinstance(key, str) or key not in _OPTION_DERIVATION_KEYS:
                allowed = ", ".join(sorted(_OPTION_DERIVATION_KEYS))
                raise ManifestError(
                    f"derivation.option_derivations.{opt_key} declares unknown "
                    f"key '{key}' (allowed: {allowed})",
                    module_name,
                )
        for section_key in ("derived_settings", "wiring_projections"):
            if section_key not in opt_value:
                continue
            section = opt_value[section_key]
            if not isinstance(section, list):
                raise ManifestError(
                    f"derivation.option_derivations.{opt_key}.{section_key} "
                    "must be a list",
                    module_name,
                )
            for index, entry in enumerate(section):
                if not isinstance(entry, dict):
                    raise ManifestError(
                        f"derivation.option_derivations.{opt_key}.{section_key}"
                        f"[{index}] must be a mapping",
                        module_name,
                    )
                _validate_derivation_entry(
                    entry,
                    f"derivation.option_derivations.{opt_key}.{section_key}[{index}]",
                    module_name,
                    wiring=section_key == "wiring_projections",
                    declared_options=declared_options,
                    option_derivations=result["option_derivations"],
                )
        if opt_key not in declared_options:
            raise ManifestError(
                f"derivation.option_derivations.{opt_key} names an undeclared option",
                module_name,
            )
    _validate_normalization_rule_list(
        result.get("normalization_rules", []),
        "derivation.normalization_rules",
        module_name,
    )
    for opt_key, opt_value in result["option_derivations"].items():
        _validate_normalization_rule_list(
            opt_value.get("normalization_rules", []),
            f"derivation.option_derivations.{opt_key}.normalization_rules",
            module_name,
        )
        for index, rule in enumerate(opt_value.get("normalization_rules") or []):
            _validate_rule_owner_keys(
                rule,
                opt_key,
                f"derivation.option_derivations.{opt_key}.normalization_rules[{index}]",
                module_name,
                require_present=True,
            )

    return result


# ---------------------------------------------------------------------------
# Implies section parsing
# ---------------------------------------------------------------------------


def _parse_implies(data: dict[str, Any], module_name: str | None) -> list[ImpliesEntry]:
    """Parse and validate the top-level ``implies`` section.

    Each entry must be a mapping with at least ``name`` (non-empty string).
    An optional ``default_config`` mapping provides configuration defaults
    for the implied module.  Returns an empty list when the section is absent.

    Args:
        data: The full parsed YAML data dictionary.
        module_name: Optional module name for error messages.

    Returns:
        A list of :class:`ImpliesEntry` instances.  Returns an empty list
        when the section is absent.

    Raises:
        ManifestError: If the section is malformed.
    """
    raw_section = data.get("implies")
    if raw_section is None:
        return []

    if not isinstance(raw_section, list):
        raise ManifestError("'implies' must be a list", module_name)

    entries: list[ImpliesEntry] = []
    for i, entry in enumerate(raw_section):
        if not isinstance(entry, dict):
            raise ManifestError(f"implies[{i}] must be a mapping", module_name)

        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ManifestError(
                f"implies[{i}].name must be a non-empty string", module_name
            )

        default_config = entry.get("default_config", {})
        if not isinstance(default_config, dict):
            raise ManifestError(
                f"implies[{i}].default_config must be a mapping", module_name
            )

        entries.append(ImpliesEntry(name=name, default_config=dict(default_config)))

    return entries


# ---------------------------------------------------------------------------
# Contract-vintage section parsing (SA10.2)
# ---------------------------------------------------------------------------


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

    steps_raw = raw.get("manual_adoption_steps", [])
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


# ---------------------------------------------------------------------------
# Project-contract vintage declaration parsing (SA207)
# ---------------------------------------------------------------------------


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

        step_id = raw_step.get("id")
        if not isinstance(step_id, str) or not step_id:
            raise ManifestError(f"'{label}.id' must be a non-empty string")
        if step_id in seen_ids:
            raise ManifestError(f"'{label}.id' duplicates {step_id!r}")
        seen_ids.add(step_id)

        minimum = _validate_declared_minimum(
            raw_step.get("minimum"), f"'{label}.minimum'"
        )

        title = raw_step.get("title")
        if not isinstance(title, str) or not title:
            raise ManifestError(f"'{label}.title' must be a non-empty string")

        adoption_raw = raw_step.get("adoption_steps")
        if not isinstance(adoption_raw, list) or not adoption_raw:
            raise ManifestError(f"'{label}.adoption_steps' must be a non-empty list")
        adoption_steps: list[str] = []
        for j, step in enumerate(adoption_raw):
            if not isinstance(step, str) or not step:
                raise ManifestError(
                    f"'{label}.adoption_steps[{j}]' must be a non-empty string"
                )
            adoption_steps.append(step)

        steps.append(
            ProjectContractStep(
                id=step_id,
                minimum=minimum,
                title=title,
                manual_adoption_steps=adoption_steps,
            )
        )

    return ProjectContractVintage(steps=steps)


def load_project_contract_vintage(
    declaration_path: Path | None = None,
) -> ProjectContractVintage:
    """Load the packaged generated-project contract declaration.

    Args:
        declaration_path: Optional override path (tests); defaults to the
            declaration shipped inside ``quickscale_core``.

    Returns:
        :class:`ProjectContractVintage`.

    Raises:
        ManifestError: If the file cannot be read or is malformed.
    """
    target = declaration_path or PROJECT_CONTRACT_DECLARATION_PATH
    try:
        content = target.read_text(encoding="utf-8")
    except OSError as error:
        raise ManifestError(
            f"Unable to read the project contract declaration {target}: {error}"
        ) from error
    data = _parse_yaml_content(content, None)
    return _parse_project_contract_vintage(data)


def load_manifest(yaml_content: str, module_name: str | None = None) -> ModuleManifest:
    """Load and validate a module manifest from YAML content

    Args:
        yaml_content: Raw YAML string
        module_name: Optional module name for error messages

    Returns:
        ModuleManifest: Validated manifest object

    Raises:
        ManifestError: If validation fails

    """
    data = _parse_yaml_content(yaml_content, module_name)

    # Validate required fields
    name = _validate_required_string_field(data, "name", module_name)
    version = _validate_required_string_field(data, "version", module_name)

    # Parse config section
    config_data = data.get("config", {})
    if not isinstance(config_data, dict):
        raise ManifestError("'config' must be a mapping", module_name)

    mutable_options = _parse_config_section(config_data, "mutable", module_name)
    immutable_options = _parse_config_section(config_data, "immutable", module_name)
    _validate_mutable_options(mutable_options, module_name)
    _validate_option_references(mutable_options, immutable_options, module_name)

    # Parse retired-option declarations (additive; empty when absent)
    retired_options = _parse_retired_options(
        data, mutable_options, immutable_options, module_name
    )

    # Parse list fields
    required_modules = _validate_list_field(data, "required_modules", module_name)
    dependencies = _validate_list_field(data, "dependencies", module_name)

    # Parse managed-files declarations (additive; empty when absent)
    managed_files = _parse_managed_files(data, module_name)

    # Parse implies declarations (additive; empty when absent)
    implies = _parse_implies(data, module_name)

    # Parse derivation section (T2.3+; additive; every field defaults to [])
    derivation = _parse_derivation_section(
        data, module_name, {**mutable_options, **immutable_options}
    )

    # Parse contract-vintage section (SA10.2; additive; None when absent)
    contract_vintage = _parse_contract_vintage(data, module_name)

    return ModuleManifest(
        name=name,
        version=version,
        description=data.get("description", ""),
        mutable_options=mutable_options,
        immutable_options=immutable_options,
        required_modules=required_modules,
        dependencies=dependencies,
        managed_files=managed_files,
        implies=implies,
        derivation_rules=derivation.get("normalization_rules", []),
        validation_rules=derivation.get("validation_rules", []),
        legacy_aliases=derivation.get("legacy_aliases", []),
        derived_settings=derivation.get("derived_settings", []),
        wiring_projections=derivation.get("wiring_projections", []),
        option_derivations=derivation.get("option_derivations", {}),
        retired_options=retired_options,
        contract_vintage=contract_vintage,
    )


def load_manifest_from_path(manifest_path: Path) -> ModuleManifest:
    """Load a module manifest from a file path

    Args:
        manifest_path: Path to module.yml file

    Returns:
        ModuleManifest: Validated manifest object

    Raises:
        ManifestError: If file not found or validation fails

    """
    if not manifest_path.exists():
        raise ManifestError(f"Manifest file not found: {manifest_path}")

    try:
        yaml_content = manifest_path.read_text()
    except OSError as e:
        raise ManifestError(f"Failed to read manifest: {e}") from e

    # Extract module name from path (parent directory name)
    module_name = manifest_path.parent.name

    return load_manifest(yaml_content, module_name)


def get_manifest_for_module(
    project_path: Path, module_name: str, *, strict: bool = False
) -> ModuleManifest | None:
    """Get manifest for an embedded module in a project

    Args:
        project_path: Path to the project root
        module_name: Name of the module
        strict: Raise for an absent module directory when true.  A present
            module directory without a manifest or with an invalid manifest
            always raises, regardless of this flag.

    Returns:
        ModuleManifest if the module has a valid manifest, or ``None`` for an
        absent module directory in non-strict mode.

    Raises:
        ManifestError: If strict mode finds no module directory, or if a
            present module is incomplete or malformed.

    """
    module_path = project_path / "modules" / module_name
    manifest_path = module_path / "module.yml"
    if not module_path.is_dir():
        if strict:
            raise ManifestError(
                f"Manifest file not found for module '{module_name}': {manifest_path}",
                module_name,
            )
        return None

    if not manifest_path.is_file():
        raise ManifestError(
            f"Manifest file not found for module '{module_name}': {manifest_path}",
            module_name,
        )

    # A present manifest is an active module state.  Structural errors must
    # remain visible in both strict and best-effort callers; only an absent
    # module directory may use the non-strict ``None`` result.
    return load_manifest_from_path(manifest_path)
