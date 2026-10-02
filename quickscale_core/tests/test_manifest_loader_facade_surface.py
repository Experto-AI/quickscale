"""Conformance gate: the split manifest loader keeps its import surface.

SA231 moved the loader implementation into sibling ``loader_*`` modules.
Every name the former ``manifest/loader.py`` module exposed at import time
must remain importable from the same module path; ``EXPECTED_MODULE_SURFACE``
records that inventory.
"""

import quickscale_core.manifest.loader as loader
from quickscale_core.manifest import (
    loader_derivation_rules,
    option_validation,
    schema,
)
from quickscale_core.manifest.derivation import NORMALIZATION_RULE_KINDS

EXPECTED_MODULE_SURFACE = frozenset(
    {
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
    }
)


def test_facade_preserves_former_module_surface() -> None:
    """Every name the former module exposed stays importable from loader."""
    missing = sorted(EXPECTED_MODULE_SURFACE - set(dir(loader)))
    assert not missing, f"facade dropped former module names: {missing}"


def test_facade_wildcard_exports_keep_former_public_names() -> None:
    """Every former public name stays in ``__all__`` for wildcard consumers."""
    former_public = {
        name for name in EXPECTED_MODULE_SURFACE if not name.startswith("_")
    }
    missing = sorted(former_public - set(loader.__all__))
    assert not missing, f"facade __all__ dropped former public names: {missing}"


def test_facade_reexports_the_original_objects() -> None:
    """Re-exported names stay identical to their defining objects."""
    assert loader.ConfigOption is schema.ConfigOption
    assert loader.ManagedFileDeclaration is schema.ManagedFileDeclaration
    assert loader.NORMALIZATION_RULE_KINDS is NORMALIZATION_RULE_KINDS
    assert loader.option_type_matches is option_validation.option_type_matches
    assert (
        loader._NORMALIZATION_RULE_COMMON_KEYS
        is loader_derivation_rules._NORMALIZATION_RULE_COMMON_KEYS
    )
    assert loader._DERIVATION_TYPES is loader_derivation_rules._DERIVATION_TYPES
