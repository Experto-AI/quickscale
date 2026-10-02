"""Module Manifest Loader

Loads and validates module.yml manifest files.
Supports optional ``derivation`` section for T2.3+ derivation/validation rules.

The parsing helpers live in the sibling ``loader_errors``, ``loader_options``,
``loader_derivation*``, and ``loader_sections`` modules; this module owns the
public entry points and re-exports every name that previously lived here, so
all existing ``quickscale_core.manifest.loader`` imports keep working.
"""

from __future__ import annotations

from pathlib import Path
import posixpath
import re
import string
from typing import Any

import yaml

from quickscale_core import __version__ as _core_version
from quickscale_core.manifest.derivation import NORMALIZATION_RULE_KINDS
from quickscale_core.manifest.loader_derivation import (
    _parse_derivation_section,
    _validate_computed_template,
    _validate_derivation_entry,
    _validate_rule_owner_keys,
    _validate_wiring_contribution,
)
from quickscale_core.manifest.loader_derivation_rules import (
    _DERIVATION_LIST_FIELDS,
    _DERIVATION_SECTION_KEYS,
    _DERIVATION_TYPES,
    _INERT_DERIVATION_SECTION_ERRORS,
    _NORMALIZATION_RULE_COMMON_KEYS,
    _NORMALIZATION_RULE_KIND_KEYS,
    _OPTION_DERIVATION_KEYS,
    _WIRING_FIELDS,
    _assert_is_list,
    _assert_is_mapping,
    _selector_chain_yields_unhashable,
    _validate_normalization_rule_list,
)
from quickscale_core.manifest.loader_errors import (
    ManifestError,
    ModuleVersionMismatchError,
)
from quickscale_core.manifest.loader_options import (
    _condition_references,
    _parse_config_option,
    _parse_config_section,
    _parse_retired_options,
    _validate_condition_mapping,
    _validate_mutable_options,
    _validate_numeric_bound,
    _validate_option_references,
    _validate_validation_block,
)
from quickscale_core.manifest.loader_sections import (
    _parse_contract_vintage,
    _parse_managed_files,
    _parse_project_contract_vintage,
    _parse_required_modules,
    _validate_declared_minimum,
)
from quickscale_core.manifest.option_validation import (
    ALLOWED_VALIDATION_KEYS,
    OPTION_TYPE_LABELS,
    option_type_matches,
)
from quickscale_core.manifest.schema import (
    MANAGED_FILE_ROOT_PREFIX,
    ConfigOption,
    ContractVintage,
    ManagedFileDeclaration,
    ModuleManifest,
    ProjectContractStep,
    ProjectContractVintage,
)

#: Packaged generated-project contract declaration (SA207).
PROJECT_CONTRACT_DECLARATION_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "project_contract.yml"
)


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
    required_modules = _parse_required_modules(data, module_name)
    dependencies = _validate_list_field(data, "dependencies", module_name)

    # Parse managed-files declarations (additive; empty when absent)
    managed_files = _parse_managed_files(data, module_name)

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


__all__ = [
    "ALLOWED_VALIDATION_KEYS",
    "Any",
    "ConfigOption",
    "ContractVintage",
    "MANAGED_FILE_ROOT_PREFIX",
    "ManagedFileDeclaration",
    "ManifestError",
    "ModuleManifest",
    "ModuleVersionMismatchError",
    "NORMALIZATION_RULE_KINDS",
    "OPTION_TYPE_LABELS",
    "PROJECT_CONTRACT_DECLARATION_PATH",
    "Path",
    "ProjectContractStep",
    "ProjectContractVintage",
    "_DERIVATION_LIST_FIELDS",
    "_DERIVATION_SECTION_KEYS",
    "_DERIVATION_TYPES",
    "_INERT_DERIVATION_SECTION_ERRORS",
    "_NORMALIZATION_RULE_COMMON_KEYS",
    "_NORMALIZATION_RULE_KIND_KEYS",
    "_OPTION_DERIVATION_KEYS",
    "_WIRING_FIELDS",
    "_assert_is_list",
    "_assert_is_mapping",
    "_condition_references",
    "_core_version",
    "_parse_canonical_version_triple",
    "_parse_config_option",
    "_parse_config_section",
    "_parse_contract_vintage",
    "_parse_derivation_section",
    "_parse_managed_files",
    "_parse_project_contract_vintage",
    "_parse_required_modules",
    "_parse_retired_options",
    "_parse_yaml_content",
    "_selector_chain_yields_unhashable",
    "_validate_computed_template",
    "_validate_condition_mapping",
    "_validate_declared_minimum",
    "_validate_derivation_entry",
    "_validate_list_field",
    "_validate_mutable_options",
    "_validate_normalization_rule_list",
    "_validate_numeric_bound",
    "_validate_option_references",
    "_validate_required_string_field",
    "_validate_rule_owner_keys",
    "_validate_validation_block",
    "_validate_wiring_contribution",
    "annotations",
    "assert_manifest_version_matches_core",
    "get_manifest_for_module",
    "load_manifest",
    "load_manifest_from_path",
    "load_project_contract_vintage",
    "option_type_matches",
    "posixpath",
    "re",
    "string",
    "yaml",
]
