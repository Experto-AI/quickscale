"""Module Manifest Derivation Schema

Companion dataclasses that describe how a module's ``module.yml`` configuration
options map to normalized values, validation constraints, legacy-key aliases,
and projected Django settings.

These types are **additive** to the existing :class:`ModuleManifest` and
:class:`ConfigOption` schema in ``schema.py``.  They do **not** extend or alter
the current manifest loader, runtime behaviour, or CLI contract-file path.
YAML serialisation and loader wiring are intentionally deferred to a later
roadmap phase; the shapes here use only simple scalars, lists, and dicts so
that future ``module.yml`` sections can be round-tripped through
``yaml.safe_load`` without custom codecs.

This foundation is the first step toward eventually replacing the imperative
``normalize_*`` / ``validate_*`` helpers and CLI contract files that currently
duplicate per-module knowledge (see roadmap Phase 4, Finding 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from dataclasses import (
    field as _field,
)  # alias to avoid name collision in WiringProjection
from typing import Any


@dataclass(frozen=True)
class NormalizationRule:
    """Declarative description of a single normalization transformation.

    A normalization rule maps a raw input value for a configuration option to
    its canonical form.  Examples include choice-value mapping
    (``"email"`` -> ``"email_only"``), case folding, whitespace stripping,
    or type coercion.

    Attributes:
        source_key: The configuration option key this rule applies to.
        target_key: The canonical output key after normalization.  Usually
            the same as *source_key*; may differ when normalization renames
            a key.
        rule_type: The kind of normalization to apply.  Recognised values
            are ``"choice_map"``, ``"lowercase"``, ``"strip"``,
            ``"coerce_int"``, ``"coerce_bool"``, and ``"identity"``.
        mapping: Optional lookup table for ``choice_map`` rules.  Keys are
            raw input values; values are the canonical outputs.
        description: Human-readable explanation of what this rule does.
    """

    source_key: str
    target_key: str
    rule_type: str
    mapping: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass(frozen=True)
class ValidationRule:
    """Declarative description of a single validation constraint.

    A validation rule expresses a constraint that a configuration option's
    value must satisfy.  Multiple rules may apply to the same option.

    Attributes:
        option_key: The configuration option key this constraint applies to.
        rule_type: The kind of validation.  Recognised values include
            ``"choices"``, ``"range"``, ``"required"``, ``"pattern"``,
            ``"min_length"``, ``"max_length"``, and ``"type"``.
        allowed_values: Permitted discrete values for ``choices`` rules.
        min_value: Inclusive lower bound for ``range`` rules.
        max_value: Inclusive upper bound for ``range`` rules.
        pattern: Regular-expression string for ``pattern`` rules.
        description: Human-readable explanation of the constraint.
    """

    option_key: str
    rule_type: str
    allowed_values: list[Any] = field(default_factory=list)
    min_value: int | float | None = None
    max_value: int | float | None = None
    pattern: str | None = None
    description: str = ""


@dataclass(frozen=True)
class LegacyKeyAlias:
    """Mapping from a deprecated configuration key to its current replacement.

    Legacy aliases allow older ``quickscale.yml`` or ``state.yml`` payloads
    that use outdated key names to be transparently migrated to the current
    schema without silent data loss.

    Attributes:
        legacy_key: The deprecated key name.
        current_key: The current canonical key name.
        transform: Optional transformation to apply to the value during
            migration.  Recognised values include ``"identity"``,
            ``"split_comma_list"``, ``"rename_value"``, and
            ``"negate_boolean"``.
        transform_params: Parameters for the chosen transform (e.g. a value
            mapping for ``rename_value``).
        description: Human-readable explanation of why this alias exists.
    """

    legacy_key: str
    current_key: str
    transform: str = "identity"
    transform_params: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass(frozen=True)
class DerivedSetting:
    """A Django setting projected from one or more configuration options.

    Derived settings describe how module configuration options translate
    into the Django ``settings.py`` keys that the module's runtime code
    reads.  This replaces the imperative derivation logic previously
    scattered across CLI contract files.

    Attributes:
        setting_key: The Django setting name (e.g.
            ``"POSTHOG_PROJECT_KEY"``).
        source_options: Configuration option keys that feed into this
            setting.  A single-option derivation has one entry; computed
            settings may combine several.
        derivation_type: How the setting value is computed.  Recognised
            values include ``"direct"`` (pass-through), ``"computed"``
            (expression-based), ``"conditional"`` (branch on a source
            value), and ``"static"`` (constant regardless of options).
        expression: YAML-friendly derivation configuration.  For
            ``"direct"`` this is typically ``{"option": "<key>"}``.
            For ``"computed"`` it may contain ``"template"`` or
            ``"format"`` strings.  For ``"conditional"`` it contains
            ``"branches"`` mapping source values to outputs.
        default: Fallback value when sources are absent or null.
        description: Human-readable explanation of what this setting
            controls.
    """

    setting_key: str
    source_options: list[str] = field(default_factory=list)
    derivation_type: str = "direct"
    expression: dict[str, Any] = field(default_factory=dict)
    default: Any = None
    description: str = ""


@dataclass(frozen=True)
class WiringProjection:
    """A wiring contribution projected from one or more configuration options.

    Wiring projections describe how module configuration options translate
    into ``ModuleWiringSpec`` fields — Django app labels, middleware dotted
    paths, and URL include tuples — that the assembler merges into the final
    spec.

    Projections use the same ``derivation_type`` vocabulary as
    :class:`DerivedSetting` (``"static"``, ``"direct"``, ``"conditional"``,
    ``"computed"``) so the same projection engine can evaluate both.

    Attributes:
        wiring_field: The :class:`~quickscale_core.module_wiring.ModuleWiringSpec`
            field this projection contributes to.  Recognised values are
            ``"apps"``, ``"middleware"``, ``"url_includes"``, and
            ``"pre_home_url_includes"``.
        source_options: Configuration option keys that determine whether and
            what to contribute.
        derivation_type: How the contribution is computed.  Uses the same
            vocabulary as :class:`DerivedSetting`.
        expression: Derivation configuration.  For ``"static"`` the value
            is a constant list/tuple contribution.  For ``"conditional"`` it
            maps source values to contribution lists.  Contributions that are
            lists of two-element lists are treated as
            ``(route_prefix, include_path)`` tuples for URL fields.
        default: Fallback contribution when sources are absent or the branch
            is unmatched.  Must be a list (of strings or two-element lists).
        description: Human-readable explanation of what this projection adds.
    """

    wiring_field: (
        str  # "apps" | "middleware" | "url_includes" | "pre_home_url_includes"
    )
    source_options: list[str] = _field(default_factory=list)
    derivation_type: str = "static"
    expression: dict[str, Any] = _field(default_factory=dict)
    default: list[Any] = _field(default_factory=list)
    description: str = ""


@dataclass(frozen=True)
class OptionDerivation:
    """Per-option derivation metadata bundling all rules for one config option.

    Groups the normalization rules, validation rules, legacy aliases,
    derived settings, and wiring projections that together describe how a
    single configuration option flows from raw user input to runtime Django
    settings and module wiring.

    Attributes:
        option_key: The configuration option key this derivation describes.
        normalization_rules: Normalization transformations for this option.
        validation_rules: Validation constraints for this option.
        legacy_aliases: Legacy key aliases that map into this option.
        derived_settings: Django settings projected from this option.
        wiring_projections: Wiring contributions projected from this option.
    """

    option_key: str
    normalization_rules: list[NormalizationRule] = field(default_factory=list)
    validation_rules: list[ValidationRule] = field(default_factory=list)
    legacy_aliases: list[LegacyKeyAlias] = field(default_factory=list)
    derived_settings: list[DerivedSetting] = field(default_factory=list)
    wiring_projections: list[WiringProjection] = field(default_factory=list)


@dataclass(frozen=True)
class ModuleDerivationSchema:
    """Top-level derivation schema for a module.

    Companion to :class:`ModuleManifest` that captures the declarative
    derivation metadata a module needs to make its ``module.yml``
    authoritative for defaults, normalization, validation, setting
    projection, legacy-key migration, and wiring projection.

    This type does **not** replace ``ModuleManifest``.  It is a parallel
    descriptor that later phases will load from a ``derivation`` section
    inside ``module.yml`` (or a sibling file) and use to replace the
    imperative contract-file logic.

    Attributes:
        module_name: The module this schema belongs to.
        version: Schema version for forward-compatibility tracking.
        option_derivations: Per-option derivation metadata keyed by
            configuration option name.
        shared_normalization_rules: Module-wide normalization rules that
            apply across multiple options (e.g. global key renaming).
        shared_validation_rules: Module-wide validation rules that apply
            across multiple options.
        module_wiring_projections: Module-level wiring projections that are
            not tied to a specific option (e.g. static app labels or
            middleware that are always contributed regardless of options).
            These are applied in addition to per-option projections.
        description: Human-readable summary of the derivation schema.
    """

    module_name: str
    version: str
    option_derivations: dict[str, OptionDerivation] = field(default_factory=dict)
    shared_normalization_rules: list[NormalizationRule] = field(default_factory=list)
    shared_validation_rules: list[ValidationRule] = field(default_factory=list)
    module_wiring_projections: list[WiringProjection] = field(default_factory=list)
    description: str = ""

    def get_option_derivation(self, option_key: str) -> OptionDerivation | None:
        """Look up the derivation metadata for a single option.

        Args:
            option_key: The configuration option key.

        Returns:
            The :class:`OptionDerivation` if present, ``None`` otherwise.
        """
        return self.option_derivations.get(option_key)

    def get_all_derived_settings(self) -> list[DerivedSetting]:
        """Collect every derived setting across all option derivations.

        Returns:
            Flat list of all :class:`DerivedSetting` instances declared
            in this schema, in option-derivation order.
        """
        settings: list[DerivedSetting] = []
        for derivation in self.option_derivations.values():
            settings.extend(derivation.derived_settings)
        return settings

    def get_all_legacy_aliases(self) -> list[LegacyKeyAlias]:
        """Collect every legacy key alias across all option derivations.

        Returns:
            Flat list of all :class:`LegacyKeyAlias` instances declared
            in this schema, in option-derivation order.
        """
        aliases: list[LegacyKeyAlias] = []
        for derivation in self.option_derivations.values():
            aliases.extend(derivation.legacy_aliases)
        return aliases

    def get_all_wiring_projections(self) -> list[WiringProjection]:
        """Collect every wiring projection across all option derivations and
        module-level projections.

        Module-level projections come first (they provide the static
        structural base), then per-option projections in option-derivation
        order.

        Returns:
            Flat list of all :class:`WiringProjection` instances declared
            in this schema.
        """
        projections: list[WiringProjection] = list(self.module_wiring_projections)
        for derivation in self.option_derivations.values():
            projections.extend(derivation.wiring_projections)
        return projections
