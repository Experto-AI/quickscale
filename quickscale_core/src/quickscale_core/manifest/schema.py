"""Module Manifest Schema

Dataclasses for module manifest (module.yml) configuration.
Defines mutable vs immutable config options for modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

#: Root prefix that all manifest-declared managed-file output paths must
#: resolve under.  This is the single source of truth for the write
#: boundary enforced by the loader and assembler.
MANAGED_FILE_ROOT_PREFIX = "quickscale_managed/"


@dataclass(frozen=True)
class ManagedFileDeclaration:
    """Declarative description of a single module-owned managed file.

    Managed files are generated artifacts that a module contributes to the
    generated project.  The declaration is intentionally minimal: a renderer
    identifier and a rooted output path.  Content generation is deferred to
    a later phase; this dataclass captures only the structural contract.

    Attributes:
        key: The YAML key identifying this managed file within the
            module's ``managed_files`` section.
        renderer: Renderer identifier (e.g. a template path or renderer
            name) that describes how the file content is produced.
        output_path: Destination path for the generated file, relative
            to the project root.  Must start with
            ``quickscale_managed/`` to enforce the write boundary.
    """

    key: str
    renderer: str
    output_path: str

    @property
    def is_within_managed_root(self) -> bool:
        """Return True when the output_path is under the managed root prefix."""
        return self.output_path.startswith(MANAGED_FILE_ROOT_PREFIX)


@dataclass
class ConfigOption:
    """Configuration option for a module"""

    name: str
    option_type: str  # boolean, string, integer, list
    default: Any = None
    django_setting: str | None = None  # Only for mutable options
    description: str = ""
    mutability: Literal["mutable", "immutable"] = "immutable"
    validation: dict[str, Any] = field(default_factory=dict)

    @property
    def is_mutable(self) -> bool:
        """Check if this option is mutable (can be changed after embed)"""
        return self.mutability == "mutable" and self.django_setting is not None


def parse_version_tuple(version_str: str) -> tuple[int, ...]:
    """Parse a dotted version string into a comparable integer tuple.

    Strips pre-release suffixes (e.g. ``"0.87.0-alpha"`` → ``"0.87.0"``)
    and maps each numeric component.  Returns ``(0,)`` for unparseable
    input so callers can fail safe (unknown < known) rather than raise.

    Example::

        >>> parse_version_tuple("0.87.0")
        (0, 87, 0)
        >>> parse_version_tuple(None)  # legacy / unknown
        (0,)
    """
    if not version_str or not isinstance(version_str, str):
        return (0,)
    try:
        core = version_str.split("-")[0]
        return tuple(int(p) for p in core.split("."))
    except ValueError, AttributeError:
        return (0,)


@dataclass
class ContractVintage:
    """Declares a module's minimum project-contract requirement.

    When the project's recorded ``project_contract`` (from ``state.yml``)
    is less than ``minimum``, the project is behind the module's contract
    and should follow ``manual_adoption_steps`` before the module is fully
    supported.

    This is the additive metadata block that powers SA10.2 detection:
    ``quickscale status`` compares each installed module's vintage
    declaration against the project's generation contract and surfaces
    the gap.

    Attributes:
        minimum: Minimum ``project_contract`` version the module expects.
            Projects with a lower (or unknown/``None``) contract value
            are flagged as behind.
        manual_adoption_steps: Human-readable list of steps an existing
            project must follow to catch up to the module's current
            contract.  Empty when no specific manual action is required.
    """

    minimum: str
    manual_adoption_steps: list[str] = field(default_factory=list)


@dataclass
class ImpliesEntry:
    """Declares that this module implies another module should also be included.

    When module A implies module B, the implication resolver (T2.2) will ensure
    module B is added to the effective module set whenever A is selected.
    An optional ``default_config`` provides configuration defaults to apply
    to the implied module.

    Attributes:
        name: The implied module name (must match a known module).
        default_config: Optional default configuration values for the
            implied module.  Keys are config option names; values are
            the defaults to apply.
    """

    name: str
    default_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModuleManifest:
    """Complete module manifest from module.yml"""

    name: str
    version: str
    description: str = ""
    mutable_options: dict[str, ConfigOption] = field(default_factory=dict)
    immutable_options: dict[str, ConfigOption] = field(default_factory=dict)
    required_modules: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    django_apps: list[str] = field(default_factory=list)
    managed_files: dict[str, ManagedFileDeclaration] = field(default_factory=dict)
    implies: list[ImpliesEntry] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Derivation metadata (T2.3+)
    #
    # These optional fields carry the derivation/validation rules that
    # instruct the resolver how to normalise, validate, project settings,
    # and wire the module from declarative ``module.yml`` data.  They are
    # populated when the loader encounters a ``derivation`` section in the
    # manifest YAML.  Existing ``module.yml`` files without a derivation
    # section leave these fields as their default empty values.
    # ------------------------------------------------------------------ #
    derivation_rules: list[dict[str, Any]] = field(default_factory=list)
    """Normalisation rules declared in the manifest derivation section."""
    validation_rules: list[dict[str, Any]] = field(default_factory=list)
    """Validation rules declared in the manifest derivation section."""
    legacy_aliases: list[dict[str, Any]] = field(default_factory=list)
    """Legacy key aliases declared in the manifest derivation section."""
    derived_settings: list[dict[str, Any]] = field(default_factory=list)
    """Derived Django settings declared in the manifest derivation section."""
    wiring_projections: list[dict[str, Any]] = field(default_factory=list)
    """Wiring projections declared in the manifest derivation section."""
    option_derivations: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Per-option derivation metadata keyed by option name. Each value is a
    raw dict with optional ``normalization_rules``, ``validation_rules``,
    ``legacy_aliases``, ``derived_settings``, and ``wiring_projections``
    sub-lists.  Populated from the ``derivation.option_derivations`` section
    in the manifest YAML."""

    # ------------------------------------------------------------------ #
    # Contract-vintage metadata (SA10.2)
    #
    # This optional field carries the module's minimum project-contract
    # requirement and the manual-adoption steps an existing project must
    # follow when its generation contract predates the module's current
    # vintage.  Populated when the loader encounters a
    # ``contract_vintage`` section in the manifest YAML.  Existing
    # ``module.yml`` files without that section leave this field as
    # ``None``.
    # ------------------------------------------------------------------ #
    contract_vintage: ContractVintage | None = None
    """Optional contract-vintage requirement for this module.
    ``None`` when the module has not declared a vintage boundary."""

    # ------------------------------------------------------------------ #
    # Readiness / lifecycle metadata
    # ------------------------------------------------------------------ #
    ready: bool = True
    """Whether the module is considered publicly ready.  Shipped modules
    with a valid ``module.yml`` default to ``True``; placeholder modules
    that lack a manifest are excluded from discovery entirely."""

    def get_option(self, option_name: str) -> ConfigOption | None:
        """Get a config option by name from either mutable or immutable"""
        if option_name in self.mutable_options:
            return self.mutable_options[option_name]
        if option_name in self.immutable_options:
            return self.immutable_options[option_name]
        return None

    def is_option_mutable(self, option_name: str) -> bool:
        """Check if a specific option is mutable"""
        return option_name in self.mutable_options

    def get_all_options(self) -> dict[str, ConfigOption]:
        """Get all config options (mutable and immutable)"""
        return {**self.mutable_options, **self.immutable_options}

    def get_defaults(self) -> dict[str, Any]:
        """Get default values for all options"""
        defaults = {}
        for name, option in self.mutable_options.items():
            defaults[name] = option.default
        for name, option in self.immutable_options.items():
            defaults[name] = option.default
        return defaults

    def get_django_settings_mapping(self) -> dict[str, str]:
        """Get mapping from option names to Django settings keys (mutable only)"""
        mapping = {}
        for name, option in self.mutable_options.items():
            if option.django_setting:
                mapping[name] = option.django_setting
        return mapping
